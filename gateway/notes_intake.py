from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from agent.auxiliary_client import async_call_llm, extract_content_or_reasoning
from hermes_cli.config import load_config
from tools.vision_tools import _detect_image_mime_type, _image_to_base64_data_url

logger = logging.getLogger(__name__)

_DEFAULT_TRANSCRIPT_DIR = Path.home() / "personal_vault" / "raw" / "transcripts" / "media"
_OCR_PYTHON = Path.home() / ".hermes" / "venvs" / "ocr" / "bin" / "python"
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)
_OCR_MIN_CONFIDENCE = 0.55


@dataclass
class NotesIntakeSettings:
    enabled: bool = True
    vision_provider: str = "main"
    vision_model: Optional[str] = None
    vision_timeout: float = 120.0
    store_temp_transcripts: bool = True
    transcript_dir: Path = _DEFAULT_TRANSCRIPT_DIR
    auto_new_session_per_capture: bool = True
    source_chat_ids: Optional[list[str]] = None
    image_classifier_engines: Optional[list[str]] = None
    clip_classifier_model: str = "openai/clip-vit-base-patch32"
    local_ocr_engines: Optional[list[str]] = None
    glm_ocr_model: str = "zai-org/GLM-OCR"
    glm_ocr_max_tokens: int = 4096

    def __post_init__(self) -> None:
        self.source_chat_ids = _normalize_source_chat_ids(self.source_chat_ids)
        self.image_classifier_engines = _normalize_image_classifier_engines(self.image_classifier_engines)
        self.local_ocr_engines = _normalize_local_ocr_engines(self.local_ocr_engines)


@dataclass
class ImageCaptureResult:
    context_block: str
    classification: dict[str, Any]
    transcript_path: Optional[str] = None


@dataclass
class TranscriptPersistResult:
    context_block: str
    artifact_path: Optional[str] = None


@dataclass
class OcrResult:
    success: bool
    text: str = ""
    engine: str = "easyocr"
    avg_confidence: Optional[float] = None
    error: Optional[str] = None


@dataclass
class VisionCallResult:
    text: str
    requested_provider: str
    requested_model: Optional[str]
    effective_provider: str
    effective_model: Optional[str]
    fallback_used: bool = False
    fallback_error: Optional[str] = None


@dataclass
class TranscriptResult:
    text: str
    engine: str
    metadata: dict[str, Any]


class NotesIntakeError(RuntimeError):
    pass


def is_anything_inbox_source(source: Any) -> bool:
    platform = getattr(getattr(source, "platform", None), "value", "") or str(getattr(source, "platform", "") or "")
    if platform != "telegram":
        return False
    chat_id = str(getattr(source, "chat_id", "") or "")
    if not chat_id:
        return False
    settings = load_notes_intake_settings()
    return chat_id in set(settings.source_chat_ids or [])


def should_auto_new_session_for_capture(source: Any) -> bool:
    """Return True when an Anything Inbox capture should run in a fresh session.

    Anything Inbox is a capture surface, not a conversational surface. Fresh
    sessions prevent unrelated notes, links, and job opportunities from
    contaminating each other's context. Related URLs should be sent together in
    one message so one agent can handle the whole bundle.
    """
    if not is_anything_inbox_source(source):
        return False
    settings = load_notes_intake_settings()
    return settings.enabled and settings.auto_new_session_per_capture


def load_notes_intake_settings() -> NotesIntakeSettings:
    cfg = load_config() or {}
    section = cfg.get("notes_intake") or {}
    transcript_dir = Path(os.path.expanduser(str(section.get("transcript_dir") or _DEFAULT_TRANSCRIPT_DIR)))
    vision_provider = str(section.get("vision_provider") or "main").strip() or "main"
    vision_model_raw = section.get("vision_model")
    if vision_model_raw is None:
        vision_model = _read_main_model_config()[1] if vision_provider == "main" else None
    else:
        vision_model = str(vision_model_raw).strip() or None
    return NotesIntakeSettings(
        enabled=bool(section.get("enabled", True)),
        vision_provider=vision_provider,
        vision_model=vision_model,
        vision_timeout=float(section.get("vision_timeout") or 120.0),
        store_temp_transcripts=bool(section.get("store_temp_transcripts", True)),
        transcript_dir=transcript_dir,
        auto_new_session_per_capture=bool(section.get("auto_new_session_per_capture", True)),
        source_chat_ids=section.get("source_chat_ids") or section.get("source_chat_id") or [],
        image_classifier_engines=section.get("image_classifier_engines") or ["local_clip", "vision"],
        clip_classifier_model=str(section.get("clip_classifier_model") or "openai/clip-vit-base-patch32").strip() or "openai/clip-vit-base-patch32",
        local_ocr_engines=section.get("local_ocr_engines") or ["glm_ocr", "easyocr"],
        glm_ocr_model=str(section.get("glm_ocr_model") or "zai-org/GLM-OCR").strip() or "zai-org/GLM-OCR",
        glm_ocr_max_tokens=int(section.get("glm_ocr_max_tokens") or 4096),
    )


def _read_main_model_config() -> tuple[str, Optional[str]]:
    cfg = load_config() or {}
    model_cfg = cfg.get("model") or {}
    provider = str(model_cfg.get("provider") or "").strip() or "auto"
    model = str(model_cfg.get("default") or "").strip() or None
    return provider, model


def _infer_effective_provider(requested_provider: str, response_model: Optional[str], *, fallback_used: bool) -> str:
    normalized = (requested_provider or "auto").strip() or "auto"
    if not fallback_used and normalized not in {"", "auto", "main"}:
        return normalized

    main_provider, main_model = _read_main_model_config()
    if response_model and main_model and response_model == main_model:
        return main_provider
    if normalized == "main":
        return main_provider
    return "auto"


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _extract_json(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if not text:
        return dict(fallback)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return dict(fallback)
    try:
        return json.loads(match.group(0))
    except Exception:
        return dict(fallback)


def _normalize_source_chat_ids(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        items = [part.strip() for part in raw_value.split(",")]
    else:
        items = [str(part).strip() for part in raw_value]
    normalized: list[str] = []
    for item in items:
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_image_classifier_engines(raw_value: Any) -> list[str]:
    if raw_value is None:
        return ["local_clip", "vision"]
    if isinstance(raw_value, str):
        items = [part.strip() for part in raw_value.split(",")]
    else:
        items = [str(part).strip() for part in raw_value]

    normalized: list[str] = []
    for item in items:
        if not item:
            continue
        engine = item.lower().replace("-", "_")
        if engine in {"clip", "local_clip", "clip_classifier"}:
            engine = "local_clip"
        elif engine == "vision":
            engine = "vision"
        if engine not in {"local_clip", "vision"}:
            logger.warning("Ignoring unknown notes-intake image classifier engine: %s", item)
            continue
        if engine not in normalized:
            normalized.append(engine)
    return normalized or ["local_clip", "vision"]


def _normalize_local_ocr_engines(raw_value: Any) -> list[str]:
    if raw_value is None:
        return ["glm_ocr", "easyocr"]
    if isinstance(raw_value, str):
        items = [part.strip() for part in raw_value.split(",")]
    else:
        items = [str(part).strip() for part in raw_value]

    normalized: list[str] = []
    for item in items:
        if not item:
            continue
        engine = item.lower().replace("-", "_")
        if engine in {"glmocr", "glm_ocr"}:
            engine = "glm_ocr"
        elif engine == "easyocr":
            engine = "easyocr"
        if engine not in {"easyocr", "glm_ocr"}:
            logger.warning("Ignoring unknown notes-intake OCR engine: %s", item)
            continue
        if engine not in normalized:
            normalized.append(engine)
    return normalized or ["glm_ocr", "easyocr"]


def _clean_ocr_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if re.fullmatch(r"<\|[^|>]+\|>", line):
            continue
        line = re.sub(r"\s*<\|[^|>]+\|>\s*", "", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _make_vision_messages(prompt: str, image_path: str) -> list[dict[str, Any]]:
    path = Path(os.path.expanduser(image_path)).resolve()
    mime_type = _detect_image_mime_type(path)
    if not mime_type:
        raise NotesIntakeError(f"Unsupported image file for notes intake: {image_path}")
    data_url = _image_to_base64_data_url(path, mime_type=mime_type)
    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]


async def _call_vision_text(
    prompt: str,
    image_path: str,
    settings: NotesIntakeSettings,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.1,
) -> VisionCallResult:
    base_kwargs: dict[str, Any] = {
        "task": "vision",
        "messages": _make_vision_messages(prompt, image_path),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": settings.vision_timeout,
    }

    preferred_provider = settings.vision_provider or "auto"
    preferred_kwargs = dict(base_kwargs)
    preferred_kwargs["provider"] = preferred_provider
    if settings.vision_model:
        preferred_kwargs["model"] = settings.vision_model

    try:
        response = await async_call_llm(**preferred_kwargs)
        effective_model = getattr(response, "model", None) or settings.vision_model
        return VisionCallResult(
            text=(extract_content_or_reasoning(response) or "").strip(),
            requested_provider=preferred_provider,
            requested_model=settings.vision_model,
            effective_provider=_infer_effective_provider(
                preferred_provider,
                effective_model,
                fallback_used=False,
            ),
            effective_model=effective_model,
        )
    except Exception as exc:
        if preferred_provider and preferred_provider != "auto":
            logger.warning(
                "Notes intake vision call failed for provider=%s model=%s; retrying with auto vision router: %s",
                preferred_provider,
                settings.vision_model,
                exc,
            )
            response = await async_call_llm(**base_kwargs)
            effective_model = getattr(response, "model", None)
            return VisionCallResult(
                text=(extract_content_or_reasoning(response) or "").strip(),
                requested_provider=preferred_provider,
                requested_model=settings.vision_model,
                effective_provider=_infer_effective_provider(
                    preferred_provider,
                    effective_model,
                    fallback_used=True,
                ),
                effective_model=effective_model,
                fallback_used=True,
                fallback_error=str(exc),
            )
        raise


def _run_local_clip_classifier(image_path: str, caption: str, settings: NotesIntakeSettings) -> dict[str, Any]:
    if not _OCR_PYTHON.exists():
        return {"success": False, "engine": "local_clip", "error": f"OCR venv missing at {_OCR_PYTHON}"}
    script = textwrap.dedent(
        """
        import json, sys
        from pathlib import Path

        model_name = sys.argv[1]
        image_path = sys.argv[2]
        caption = sys.argv[3]

        prompts = [
            ("handwritten_note", "a smartphone photo of handwritten notes on paper or a notebook page"),
            ("document_scan", "a scan or photo of a printed document page, form, or receipt"),
            ("screenshot", "a computer or phone screenshot of an app, website, or user interface"),
            ("diagram", "a diagram, chart, graph, slide, whiteboard, or technical figure"),
            ("photo", "a natural photo of a scene, object, person, or real world setting"),
            ("mixed", "a mixed image containing both substantial text and graphics or UI elements"),
            ("other", "some other kind of image that does not fit the main note categories"),
        ]

        try:
            import torch
            from PIL import Image
            from transformers import AutoProcessor, CLIPModel
        except Exception as exc:
            print(json.dumps({"success": False, "engine": "local_clip", "error": f"local clip import failed: {exc}"}, ensure_ascii=False))
            raise SystemExit(0)

        try:
            processor = AutoProcessor.from_pretrained(model_name)
            model = CLIPModel.from_pretrained(model_name)
            image = Image.open(Path(image_path)).convert("RGB")
            texts = [prompt for _, prompt in prompts]
            inputs = processor(text=texts, images=image, return_tensors="pt", padding=True)
            with torch.inference_mode():
                logits = model(**inputs).logits_per_image[0]
                probs = logits.softmax(dim=0)
            best_index = int(probs.argmax().item())
            kind = prompts[best_index][0]
            score = float(probs[best_index].item())
            should_run_ocr = kind in {"handwritten_note", "document_scan", "mixed"}
            should_run_summary = kind in {"screenshot", "diagram", "mixed"}
            reason = f"local clip matched {kind} with score {score:.3f}"
            if caption:
                reason += f"; caption hint: {caption[:120]}"
            print(json.dumps({
                "success": True,
                "engine": "local_clip",
                "kind": kind,
                "score": score,
                "should_run_ocr": should_run_ocr,
                "should_run_summary": should_run_summary,
                "reason": reason,
            }, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"success": False, "engine": "local_clip", "error": str(exc)}, ensure_ascii=False))
        """
    ).strip()
    try:
        proc = subprocess.run(
            [str(_OCR_PYTHON), "-c", script, settings.clip_classifier_model, image_path, caption or ""],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:
        return {"success": False, "engine": "local_clip", "error": str(exc)}

    output = (proc.stdout or "").strip().splitlines()
    payload = output[-1] if output else ""
    try:
        data = json.loads(payload)
    except Exception:
        data = {"success": False, "engine": "local_clip", "error": f"invalid classifier output: {(proc.stdout or proc.stderr or '').strip()[:300]}"}
    return data


def _run_local_image_classifier(engine: str, image_path: str, caption: str, settings: NotesIntakeSettings) -> dict[str, Any]:
    if engine == "local_clip":
        return _run_local_clip_classifier(image_path, caption, settings)
    return {"success": False, "engine": engine, "error": f"unsupported classifier engine: {engine}"}


async def classify_image_for_notes(image_path: str, caption: str, settings: NotesIntakeSettings) -> dict[str, Any]:
    prompt = textwrap.dedent(
        f"""
        You are classifying an image sent to a personal notes inbox.
        Caption or surrounding user text:
        {caption or "<empty>"}

        Return strict JSON only with this schema:
        {{
          "kind": "handwritten_note|document_scan|screenshot|diagram|photo|mixed|other",
          "should_run_ocr": true,
          "should_run_summary": false,
          "reason": "short explanation"
        }}

        Rules:
        - handwritten_note/document_scan => should_run_ocr true.
        - screenshot/diagram => should_run_summary true.
        - mixed => both true.
        - Prefer OCR for text-heavy note pages, whiteboards, notebook photos, printed pages, receipts, or blackboard notes.
        - Prefer summary for UI screenshots, plots, slides, diagrams, memes, photos, or scenes.
        """
    ).strip()
    fallback = {
        "kind": "mixed",
        "should_run_ocr": True,
        "should_run_summary": True,
        "reason": "Fallback classification after classifier failure.",
    }
    attempted_engines: list[str] = []
    local_errors: list[str] = []

    for engine_name in settings.image_classifier_engines:
        attempted_engines.append(engine_name)
        if engine_name == "vision":
            try:
                call = await _call_vision_text(prompt, image_path, settings, max_tokens=400)
                parsed = _extract_json(call.text, fallback)
                parsed["classification_engine"] = "vision"
                parsed["classification_engines_tried"] = attempted_engines
                if local_errors:
                    parsed["classification_local_error"] = "; ".join(local_errors)
                parsed["vision_requested_provider"] = call.requested_provider
                parsed["vision_requested_model"] = call.requested_model
                parsed["vision_effective_provider"] = call.effective_provider
                parsed["vision_effective_model"] = call.effective_model
                parsed["vision_fallback_used"] = call.fallback_used
                parsed["vision_fallback_error"] = call.fallback_error
                break
            except Exception as exc:
                logger.warning("Notes intake vision classifier failed for %s: %s", image_path, exc)
                local_errors.append(f"vision: {exc}")
                parsed = dict(fallback)
                continue

        local_result = await asyncio.to_thread(_run_local_image_classifier, engine_name, image_path, caption, settings)
        if bool(local_result.get("success")):
            parsed = {
                "kind": str(local_result.get("kind") or fallback["kind"]),
                "should_run_ocr": bool(local_result.get("should_run_ocr", fallback["should_run_ocr"])),
                "should_run_summary": bool(local_result.get("should_run_summary", fallback["should_run_summary"])),
                "reason": str(local_result.get("reason") or fallback["reason"]),
                "classification_engine": str(local_result.get("engine") or engine_name),
                "classification_score": local_result.get("score"),
                "classification_engines_tried": attempted_engines,
            }
            break

        error_text = str(local_result.get("error") or "classifier returned no result").strip()
        local_errors.append(error_text)
    else:
        logger.warning("Notes intake classifier failed for %s: %s", image_path, '; '.join(local_errors) or 'all classifiers failed')
        parsed = dict(fallback)
        parsed["classification_engines_tried"] = attempted_engines
        if local_errors:
            parsed["classification_local_error"] = "; ".join(local_errors)

    parsed.setdefault("kind", fallback["kind"])
    parsed.setdefault("should_run_ocr", fallback["should_run_ocr"])
    parsed.setdefault("should_run_summary", fallback["should_run_summary"])
    parsed.setdefault("reason", fallback["reason"])
    return parsed


def _run_easyocr(image_path: str) -> OcrResult:
    if not _OCR_PYTHON.exists():
        return OcrResult(success=False, engine="easyocr", error=f"OCR venv missing at {_OCR_PYTHON}")
    script = textwrap.dedent(
        """
        import json, sys
        try:
            import easyocr
        except Exception as exc:
            print(json.dumps({"success": False, "error": f"easyocr import failed: {exc}"}, ensure_ascii=False))
            raise SystemExit(0)
        path = sys.argv[1]
        try:
            reader = easyocr.Reader(['en', 'es'], gpu=False)
            rows = reader.readtext(path, detail=1, paragraph=False)
            text = "\\n".join((row[1] or "").strip() for row in rows if len(row) >= 2 and (row[1] or "").strip()).strip()
            confs = [float(row[2]) for row in rows if len(row) >= 3 and isinstance(row[2], (int, float))]
            avg_conf = sum(confs) / len(confs) if confs else None
            print(json.dumps({
                "success": bool(text),
                "text": text,
                "avg_confidence": avg_conf,
                "engine": "easyocr",
                "error": None if text else "OCR returned empty text",
            }, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"success": False, "error": str(exc), "engine": "easyocr"}, ensure_ascii=False))
        """
    ).strip()
    try:
        proc = subprocess.run(
            [str(_OCR_PYTHON), "-c", script, image_path],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        return OcrResult(success=False, engine="easyocr", error=str(exc))

    output = (proc.stdout or "").strip().splitlines()
    payload = output[-1] if output else ""
    try:
        data = json.loads(payload)
    except Exception:
        data = {"success": False, "error": f"invalid OCR output: {(proc.stdout or proc.stderr or '').strip()[:300]}"}
    return OcrResult(
        success=bool(data.get("success")),
        text=_clean_ocr_text(str(data.get("text") or "")),
        engine=str(data.get("engine") or "easyocr"),
        avg_confidence=data.get("avg_confidence"),
        error=str(data.get("error") or "").strip() or None,
    )


def _run_glm_ocr(image_path: str, settings: NotesIntakeSettings) -> OcrResult:
    if not _OCR_PYTHON.exists():
        return OcrResult(success=False, engine="glm_ocr", error=f"OCR venv missing at {_OCR_PYTHON}")
    script = textwrap.dedent(
        """
        import json, sys
        from pathlib import Path

        model_path = sys.argv[1]
        image_path = sys.argv[2]
        max_tokens = int(sys.argv[3])
        prompt = sys.argv[4]

        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except Exception as exc:
            print(json.dumps({"success": False, "error": f"glm_ocr import failed: {exc}", "engine": "glm_ocr"}, ensure_ascii=False))
            raise SystemExit(0)

        try:
            processor = AutoProcessor.from_pretrained(model_path)
            model = AutoModelForImageTextToText.from_pretrained(
                pretrained_model_name_or_path=model_path,
                torch_dtype="auto",
                device_map="auto",
            )
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "url": str(Path(image_path))},
                    {"type": "text", "text": prompt},
                ],
            }]
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            ).to(model.device)
            inputs.pop("token_type_ids", None)
            with torch.inference_mode():
                generated_ids = model.generate(**inputs, max_new_tokens=max_tokens)
            generated = generated_ids[0][inputs["input_ids"].shape[1]:]
            text = processor.decode(generated, skip_special_tokens=False).strip()
            print(json.dumps({
                "success": bool(text),
                "text": text,
                "avg_confidence": None,
                "engine": "glm_ocr",
                "error": None if text else "GLM-OCR returned empty text",
            }, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"success": False, "error": str(exc), "engine": "glm_ocr"}, ensure_ascii=False))
        """
    ).strip()
    try:
        proc = subprocess.run(
            [
                str(_OCR_PYTHON),
                "-c",
                script,
                settings.glm_ocr_model,
                image_path,
                str(settings.glm_ocr_max_tokens),
                "Text Recognition:",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except Exception as exc:
        return OcrResult(success=False, engine="glm_ocr", error=str(exc))

    output = (proc.stdout or "").strip().splitlines()
    payload = output[-1] if output else ""
    try:
        data = json.loads(payload)
    except Exception:
        data = {"success": False, "error": f"invalid OCR output: {(proc.stdout or proc.stderr or '').strip()[:300]}", "engine": "glm_ocr"}
    return OcrResult(
        success=bool(data.get("success")),
        text=_clean_ocr_text(str(data.get("text") or "")),
        engine=str(data.get("engine") or "glm_ocr"),
        avg_confidence=data.get("avg_confidence"),
        error=str(data.get("error") or "").strip() or None,
    )


def _run_local_ocr_engine(engine: str, image_path: str, settings: NotesIntakeSettings) -> OcrResult:
    runners: dict[str, Callable[..., OcrResult]] = {
        "easyocr": _run_easyocr,
        "glm_ocr": _run_glm_ocr,
    }
    runner = runners.get(engine)
    if runner is None:
        return OcrResult(success=False, engine=engine, error=f"unsupported OCR engine: {engine}")
    if engine == "glm_ocr":
        return runner(image_path, settings)
    return runner(image_path)


async def transcribe_note_image(image_path: str, caption: str, settings: NotesIntakeSettings) -> TranscriptResult:
    attempted_engines: list[str] = []
    local_failures: list[str] = []
    last_ocr: Optional[OcrResult] = None

    for engine_name in settings.local_ocr_engines:
        attempted_engines.append(engine_name)
        ocr = await asyncio.to_thread(_run_local_ocr_engine, engine_name, image_path, settings)
        last_ocr = ocr
        text = _clean_ocr_text(ocr.text)
        ocr_is_strong = bool(text) and (
            ocr.avg_confidence is None or float(ocr.avg_confidence) >= _OCR_MIN_CONFIDENCE
        )
        if ocr_is_strong:
            return TranscriptResult(
                text=text,
                engine=ocr.engine,
                metadata={
                    "ocr_engine": ocr.engine,
                    "ocr_avg_confidence": ocr.avg_confidence,
                    "ocr_fallback_used": False,
                    "ocr_local_engines_tried": attempted_engines,
                },
            )

        weak_reason = ocr.error
        if text and ocr.avg_confidence is not None and float(ocr.avg_confidence) < _OCR_MIN_CONFIDENCE:
            weak_reason = f"weak OCR confidence {ocr.avg_confidence:.3f} < {_OCR_MIN_CONFIDENCE:.2f}"
        local_failures.append(f"{engine_name}: {weak_reason or 'OCR returned empty text'}")

    weak_reason = "; ".join(local_failures) if local_failures else "all local OCR engines failed"
    logger.info("Notes intake OCR fallback to vision transcription for %s (%s)", image_path, weak_reason)
    prompt = textwrap.dedent(
        f"""
        Transcribe all visible handwritten and printed text from this image as faithfully as possible.
        Caption or surrounding user text: {caption or "<empty>"}

        Output plain text only.
        Preserve line breaks when they matter.
        If a short fragment is unreadable, mark it as [unclear].
        Do not summarize or explain the image.
        """
    ).strip()
    call = await _call_vision_text(prompt, image_path, settings, max_tokens=1600, temperature=0.0)
    engine = "vision-ocr"
    if call.effective_provider and call.effective_model:
        engine = f"{call.effective_provider}:{call.effective_model}"
    elif call.effective_provider:
        engine = f"{call.effective_provider}:vision"
    return TranscriptResult(
        text=_clean_ocr_text(call.text),
        engine=engine,
        metadata={
            "ocr_engine": engine,
            "ocr_local_error": weak_reason,
            "ocr_local_engine": last_ocr.engine if last_ocr else None,
            "ocr_local_engines_tried": attempted_engines,
            "ocr_requested_provider": call.requested_provider,
            "ocr_requested_model": call.requested_model,
            "ocr_effective_provider": call.effective_provider,
            "ocr_effective_model": call.effective_model,
            "ocr_fallback_used": True,
            "ocr_fallback_error": call.fallback_error,
        },
    )


async def summarize_non_note_image(image_path: str, caption: str, settings: NotesIntakeSettings) -> str:
    prompt = textwrap.dedent(
        f"""
        This image was sent into a personal notes inbox.
        Caption or surrounding user text: {caption or "<empty>"}

        Produce a concise but information-dense summary for downstream note filing.
        Include:
        - what kind of image this is,
        - any visible text worth preserving,
        - the main concepts, UI elements, chart contents, or relationships,
        - anything relevant for later retrieval.

        Do not mention that you are an AI model.
        """
    ).strip()
    call = await _call_vision_text(prompt, image_path, settings, max_tokens=1400)
    return call.text


def persist_transcript_artifact(kind: str, source_path: str, content: str, *, settings: NotesIntakeSettings, metadata: Optional[dict[str, Any]] = None) -> Optional[str]:
    if not settings.store_temp_transcripts:
        return None
    cleaned = (content or "").strip()
    if not cleaned:
        return None
    metadata = metadata or {}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(source_path).stem).strip("-") or kind
    target_dir = settings.transcript_dir / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{timestamp}-{kind}-{stem}.md"
    lines = [
        "---",
        f"kind: {kind}",
        f"created_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"source_media_path: {source_path}",
    ]
    for key in sorted(metadata):
        value = metadata[key]
        if value is None or value == "":
            continue
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.extend(["---", "", cleaned, ""])
    target.write_text("\n".join(lines), encoding="utf-8")
    return str(target)


async def enrich_anything_inbox_image(image_path: str, user_text: str, settings: Optional[NotesIntakeSettings] = None) -> ImageCaptureResult:
    settings = settings or load_notes_intake_settings()
    classification = await classify_image_for_notes(image_path, user_text, settings)
    should_run_ocr = bool(classification.get("should_run_ocr"))
    should_run_summary = bool(classification.get("should_run_summary"))
    kind = str(classification.get("kind") or "mixed")

    transcript_text = ""
    transcript_engine = ""
    transcript_metadata: dict[str, Any] = {}
    transcript_path = None
    if should_run_ocr:
        transcript_result = await transcribe_note_image(image_path, user_text, settings)
        transcript_text = transcript_result.text
        transcript_engine = transcript_result.engine
        transcript_metadata = dict(transcript_result.metadata)
        transcript_path = persist_transcript_artifact(
            "image-ocr",
            image_path,
            transcript_text,
            settings=settings,
            metadata={
                "classification_kind": kind,
                **transcript_metadata,
            },
        )

    summary_text = ""
    if should_run_summary or (not transcript_text and kind in {"screenshot", "diagram", "photo", "mixed", "other"}):
        summary_text = await summarize_non_note_image(image_path, user_text, settings)

    lines = [
        "[NOTES INBOX MEDIA ANALYSIS]",
        f"capture_modality: image",
        f"classification_kind: {kind}",
        f"classification_engine: {classification.get('classification_engine', '')}",
        f"classification_reason: {classification.get('reason', '')}",
        f"saved_media_path: {image_path}",
    ]
    if classification.get("vision_effective_provider"):
        lines.append(f"classification_provider: {classification.get('vision_effective_provider')}")
    if classification.get("vision_effective_model"):
        lines.append(f"classification_model: {classification.get('vision_effective_model')}")
    if classification.get("vision_fallback_error"):
        lines.append(f"classification_fallback_error: {classification.get('vision_fallback_error')}")
    if transcript_path:
        lines.append(f"capture_artifact_path: {transcript_path}")
    if transcript_text:
        lines.append(f"ocr_engine: {transcript_engine}")
        if transcript_metadata.get("ocr_effective_provider"):
            lines.append(f"ocr_provider: {transcript_metadata.get('ocr_effective_provider')}")
        if transcript_metadata.get("ocr_effective_model"):
            lines.append(f"ocr_model: {transcript_metadata.get('ocr_effective_model')}")
        if transcript_metadata.get("ocr_fallback_error"):
            lines.append(f"ocr_fallback_error: {transcript_metadata.get('ocr_fallback_error')}")
        lines.extend([
            "ocr_transcript:",
            transcript_text,
        ])
    if summary_text:
        lines.extend([
            "image_summary:",
            summary_text,
        ])
    lines.append("[END NOTES INBOX MEDIA ANALYSIS]")
    return ImageCaptureResult(
        context_block="\n".join(lines).strip(),
        classification=classification,
        transcript_path=transcript_path,
    )


def persist_audio_transcript(user_text: str, audio_path: str, transcript: str, *, provider: Optional[str] = None, settings: Optional[NotesIntakeSettings] = None) -> TranscriptPersistResult:
    settings = settings or load_notes_intake_settings()
    artifact_path = persist_transcript_artifact(
        "audio-transcript",
        audio_path,
        transcript,
        settings=settings,
        metadata={"transcript_provider": provider or "unknown"},
    )
    lines = [
        "[NOTES INBOX MEDIA ANALYSIS]",
        "capture_modality: audio",
        f"saved_media_path: {audio_path}",
    ]
    if artifact_path:
        lines.append(f"capture_artifact_path: {artifact_path}")
    lines.extend([
        "audio_transcript:",
        transcript,
        "[END NOTES INBOX MEDIA ANALYSIS]",
    ])
    return TranscriptPersistResult(context_block="\n".join(lines), artifact_path=artifact_path)
