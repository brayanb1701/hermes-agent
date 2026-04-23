from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource


@pytest.mark.asyncio
async def test_prepare_inbound_message_text_uses_notes_intake_pipeline_for_anything_inbox_images():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(stt_enabled=True)
    runner.adapters = {}
    runner._model = "test-model"
    runner._base_url = ""
    runner._has_setup_skill = lambda: False

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="test-notes-chat",
        chat_type="group",
        user_name="Brayan",
    )
    event = MessageEvent(
        text="file this",
        message_type=MessageType.PHOTO,
        source=source,
        media_urls=["/tmp/note-photo.png"],
        media_types=["image/png"],
    )

    with (
        patch("gateway.run.load_notes_intake_settings", return_value=SimpleNamespace(enabled=True)),
        patch("gateway.run.is_anything_inbox_source", return_value=True),
        patch("gateway.run.enrich_anything_inbox_image", new=AsyncMock(return_value=SimpleNamespace(context_block="[NOTES INBOX MEDIA ANALYSIS]\nocr_transcript:\nhello\n[END NOTES INBOX MEDIA ANALYSIS]"))) as enrich_mock,
        patch.object(runner, "_enrich_message_with_vision", new=AsyncMock(side_effect=AssertionError("generic vision path should not run"))),
    ):
        result = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    enrich_mock.assert_awaited_once_with("/tmp/note-photo.png", "file this")
    assert "ocr_transcript" in result
    assert result.endswith("file this")


@pytest.mark.asyncio
async def test_prepare_inbound_message_text_falls_back_to_generic_vision_when_notes_intake_image_enrichment_fails():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(stt_enabled=True)
    runner.adapters = {}
    runner._model = "test-model"
    runner._base_url = ""
    runner._has_setup_skill = lambda: False

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="test-notes-chat",
        chat_type="group",
        user_name="Brayan",
    )
    event = MessageEvent(
        text="file this",
        message_type=MessageType.PHOTO,
        source=source,
        media_urls=["/tmp/note-photo.png"],
        media_types=["image/png"],
    )

    with (
        patch("gateway.run.load_notes_intake_settings", return_value=SimpleNamespace(enabled=True)),
        patch("gateway.run.is_anything_inbox_source", return_value=True),
        patch("gateway.run.enrich_anything_inbox_image", new=AsyncMock(side_effect=RuntimeError("ocr failed"))),
        patch.object(runner, "_enrich_message_with_vision", new=AsyncMock(return_value='[The user sent 1 image(s): generic summary]')) as vision_mock,
    ):
        result = await runner._prepare_inbound_message_text(event=event, source=source, history=[])

    vision_mock.assert_awaited_once_with("", ["/tmp/note-photo.png"])
    assert "fallback_vision_summary" in result
    assert "generic summary" in result
    assert result.endswith("file this")


@pytest.mark.asyncio
async def test_enrich_message_with_transcription_persists_anything_inbox_audio_transcript():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(stt_enabled=True)
    runner._has_setup_skill = lambda: False

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="test-notes-chat",
        chat_type="group",
    )

    with (
        patch("tools.transcription_tools.transcribe_audio", return_value={"success": True, "transcript": "voice transcript", "provider": "local_command"}),
        patch("gateway.run.load_notes_intake_settings", return_value=SimpleNamespace(enabled=True)),
        patch("gateway.run.is_anything_inbox_source", return_value=True),
        patch("gateway.run.persist_audio_transcript", return_value=SimpleNamespace(context_block="[NOTES INBOX MEDIA ANALYSIS]\naudio_transcript:\nvoice transcript\n[END NOTES INBOX MEDIA ANALYSIS]", artifact_path="/tmp/transcript.md")) as persist_mock,
    ):
        result = await runner._enrich_message_with_transcription(
            "caption",
            ["/tmp/voice.ogg"],
            source=source,
        )

    persist_mock.assert_called_once_with(
        "caption",
        "/tmp/voice.ogg",
        "voice transcript",
        provider="local_command",
    )
    assert "audio_transcript" in result
    assert result.endswith("caption")


def test_run_easyocr_embeds_literal_backslash_n_in_subprocess_script(tmp_path, monkeypatch):
    from gateway import notes_intake

    fake_python = tmp_path / "python"
    fake_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(notes_intake, "_OCR_PYTHON", fake_python)

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return SimpleNamespace(stdout='{"success": true, "text": "ok", "engine": "easyocr", "avg_confidence": 0.9}\n', stderr="")

    monkeypatch.setattr(notes_intake.subprocess, "run", fake_run)

    result = notes_intake._run_easyocr("/tmp/example.png")

    assert result.success is True
    assert result.text == "ok"
    assert '"\\n".join' in captured["args"][2]


@pytest.mark.asyncio
async def test_call_vision_text_records_auto_fallback_metadata():
    from gateway import notes_intake

    settings = notes_intake.NotesIntakeSettings(
        vision_provider="copilot",
        vision_model="gpt-4.1",
        vision_timeout=30,
    )
    response = SimpleNamespace(model="gpt-5.4")

    with (
        patch.object(notes_intake, "_make_vision_messages", return_value=[{"role": "user", "content": []}]),
        patch.object(
            notes_intake,
            "async_call_llm",
            new=AsyncMock(side_effect=[RuntimeError("forbidden"), response]),
        ),
        patch.object(notes_intake, "extract_content_or_reasoning", return_value="OK"),
        patch.object(notes_intake, "_read_main_model_config", return_value=("openai-codex", "gpt-5.4")),
    ):
        result = await notes_intake._call_vision_text("prompt", "/tmp/example.png", settings)

    assert result.text == "OK"
    assert result.requested_provider == "copilot"
    assert result.requested_model == "gpt-4.1"
    assert result.effective_provider == "openai-codex"
    assert result.effective_model == "gpt-5.4"
    assert result.fallback_used is True
    assert result.fallback_error == "forbidden"


def test_load_notes_intake_settings_reads_local_ocr_configuration(monkeypatch):
    from gateway import notes_intake

    monkeypatch.setattr(
        notes_intake,
        "load_config",
        lambda: {
            "notes_intake": {
                "enabled": True,
                "vision_provider": "main",
                "vision_model": "gpt-5.4-mini",
                "source_chat_ids": ["test-notes-chat"],
                "image_classifier_engines": ["local_clip", "vision"],
                "clip_classifier_model": "openai/clip-vit-base-patch32",
                "local_ocr_engines": ["glm_ocr", "easyocr"],
                "glm_ocr_model": "zai-org/GLM-OCR",
                "glm_ocr_max_tokens": 4096,
            }
        },
    )

    settings = notes_intake.load_notes_intake_settings()

    assert settings.source_chat_ids == ["test-notes-chat"]
    assert settings.image_classifier_engines == ["local_clip", "vision"]
    assert settings.clip_classifier_model == "openai/clip-vit-base-patch32"
    assert settings.local_ocr_engines == ["glm_ocr", "easyocr"]
    assert settings.glm_ocr_model == "zai-org/GLM-OCR"
    assert settings.glm_ocr_max_tokens == 4096


def test_notes_intake_auto_new_session_setting_controls_anything_inbox(monkeypatch):
    from gateway import notes_intake

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="test-notes-chat",
        chat_type="group",
    )

    monkeypatch.setattr(
        notes_intake,
        "load_config",
        lambda: {"notes_intake": {"enabled": True, "auto_new_session_per_capture": True, "source_chat_ids": ["test-notes-chat"]}},
    )
    settings = notes_intake.load_notes_intake_settings()
    assert settings.auto_new_session_per_capture is True
    assert notes_intake.should_auto_new_session_for_capture(source) is True

    monkeypatch.setattr(
        notes_intake,
        "load_config",
        lambda: {"notes_intake": {"enabled": True, "auto_new_session_per_capture": False, "source_chat_ids": ["test-notes-chat"]}},
    )
    assert notes_intake.should_auto_new_session_for_capture(source) is False


@pytest.mark.asyncio
async def test_classify_image_for_notes_uses_local_classifier_before_vision():
    from gateway import notes_intake

    settings = notes_intake.NotesIntakeSettings(
        image_classifier_engines=["local_clip", "vision"],
        clip_classifier_model="openai/clip-vit-base-patch32",
        vision_provider="main",
        vision_model="gpt-5.4-mini",
    )

    local_result = {
        "success": True,
        "kind": "handwritten_note",
        "should_run_ocr": True,
        "should_run_summary": False,
        "reason": "local clip matched handwritten notebook page",
        "engine": "local_clip",
        "score": 0.91,
    }

    with (
        patch.object(notes_intake.asyncio, "to_thread", new=AsyncMock(return_value=local_result)),
        patch.object(notes_intake, "_call_vision_text", new=AsyncMock(side_effect=AssertionError("vision classifier should not run when local classifier succeeds"))),
    ):
        result = await notes_intake.classify_image_for_notes("/tmp/example.png", "caption", settings)

    assert result["kind"] == "handwritten_note"
    assert result["should_run_ocr"] is True
    assert result["should_run_summary"] is False
    assert result["classification_engine"] == "local_clip"
    assert result["classification_score"] == 0.91
    assert result["classification_engines_tried"] == ["local_clip"]


@pytest.mark.asyncio
async def test_classify_image_for_notes_falls_back_to_vision_when_local_classifier_fails():
    from gateway import notes_intake

    settings = notes_intake.NotesIntakeSettings(
        image_classifier_engines=["local_clip", "vision"],
        clip_classifier_model="openai/clip-vit-base-patch32",
        vision_provider="main",
        vision_model="gpt-5.4-mini",
    )

    local_result = {
        "success": False,
        "error": "local classifier unavailable",
        "engine": "local_clip",
    }
    vision_result = notes_intake.VisionCallResult(
        text='{"kind":"screenshot","should_run_ocr":false,"should_run_summary":true,"reason":"ui screenshot"}',
        requested_provider="main",
        requested_model="gpt-5.4-mini",
        effective_provider="openai-codex",
        effective_model="gpt-5.4-mini",
        fallback_used=False,
        fallback_error=None,
    )

    with (
        patch.object(notes_intake.asyncio, "to_thread", new=AsyncMock(return_value=local_result)),
        patch.object(notes_intake, "_call_vision_text", new=AsyncMock(return_value=vision_result)),
    ):
        result = await notes_intake.classify_image_for_notes("/tmp/example.png", "caption", settings)

    assert result["kind"] == "screenshot"
    assert result["should_run_ocr"] is False
    assert result["should_run_summary"] is True
    assert result["classification_engine"] == "vision"
    assert result["classification_engines_tried"] == ["local_clip", "vision"]
    assert result["classification_local_error"] == "local classifier unavailable"


def test_clean_ocr_text_strips_generation_artifacts():
    from gateway import notes_intake

    cleaned = notes_intake._clean_ocr_text("Hello world\n<|user|>\n<|assistant|>\n")

    assert cleaned == "Hello world"


@pytest.mark.asyncio
async def test_transcribe_note_image_uses_glm_ocr_first_when_it_succeeds():
    from gateway import notes_intake

    settings = notes_intake.NotesIntakeSettings(
        vision_provider="main",
        vision_model="gpt-5.4",
        vision_timeout=30,
        local_ocr_engines=["glm_ocr", "easyocr"],
        glm_ocr_model="zai-org/GLM-OCR",
        glm_ocr_max_tokens=4096,
    )

    glm_result = notes_intake.OcrResult(
        success=True,
        text="strong local transcript<|user|>",
        engine="glm_ocr",
        avg_confidence=None,
        error=None,
    )

    to_thread_mock = AsyncMock(return_value=glm_result)
    vision_mock = AsyncMock(side_effect=AssertionError("vision fallback should not run when glm_ocr succeeds"))

    with (
        patch.object(notes_intake.asyncio, "to_thread", new=to_thread_mock),
        patch.object(notes_intake, "_call_vision_text", new=vision_mock),
    ):
        result = await notes_intake.transcribe_note_image("/tmp/example.png", "caption", settings)

    assert result.text == "strong local transcript"
    assert result.engine == "glm_ocr"
    assert result.metadata["ocr_engine"] == "glm_ocr"
    assert result.metadata["ocr_local_engines_tried"] == ["glm_ocr"]
    assert result.metadata["ocr_fallback_used"] is False


@pytest.mark.asyncio
async def test_transcribe_note_image_falls_back_to_easyocr_after_glm_ocr_fails():
    from gateway import notes_intake

    settings = notes_intake.NotesIntakeSettings(
        vision_provider="main",
        vision_model="gpt-5.4",
        vision_timeout=30,
        local_ocr_engines=["glm_ocr", "easyocr"],
        glm_ocr_model="zai-org/GLM-OCR",
        glm_ocr_max_tokens=4096,
    )

    glm_result = notes_intake.OcrResult(
        success=False,
        text="",
        engine="glm_ocr",
        avg_confidence=None,
        error="glm failed",
    )
    easyocr_result = notes_intake.OcrResult(
        success=True,
        text="easy transcript",
        engine="easyocr",
        avg_confidence=0.92,
        error=None,
    )

    to_thread_mock = AsyncMock(side_effect=[glm_result, easyocr_result])
    vision_mock = AsyncMock(side_effect=AssertionError("vision fallback should not run when easyocr succeeds"))

    with (
        patch.object(notes_intake.asyncio, "to_thread", new=to_thread_mock),
        patch.object(notes_intake, "_call_vision_text", new=vision_mock),
    ):
        result = await notes_intake.transcribe_note_image("/tmp/example.png", "caption", settings)

    assert result.text == "easy transcript"
    assert result.engine == "easyocr"
    assert result.metadata["ocr_local_engines_tried"] == ["glm_ocr", "easyocr"]
    assert result.metadata["ocr_fallback_used"] is False


@pytest.mark.asyncio
async def test_transcribe_note_image_falls_back_to_vision_after_local_ocr_engines_fail():
    from gateway import notes_intake

    settings = notes_intake.NotesIntakeSettings(
        vision_provider="main",
        vision_model="gpt-5.4",
        vision_timeout=30,
        local_ocr_engines=["glm_ocr", "easyocr"],
        glm_ocr_model="zai-org/GLM-OCR",
        glm_ocr_max_tokens=4096,
    )

    glm_result = notes_intake.OcrResult(
        success=False,
        text="",
        engine="glm_ocr",
        avg_confidence=None,
        error="glm_ocr unavailable",
    )
    easyocr_result = notes_intake.OcrResult(
        success=True,
        text="garbled text",
        engine="easyocr",
        avg_confidence=0.2,
        error=None,
    )
    vision_result = notes_intake.VisionCallResult(
        text="clean transcript",
        requested_provider="main",
        requested_model="gpt-5.4",
        effective_provider="openai-codex",
        effective_model="gpt-5.4",
        fallback_used=False,
        fallback_error=None,
    )

    with (
        patch.object(notes_intake.asyncio, "to_thread", new=AsyncMock(side_effect=[glm_result, easyocr_result])),
        patch.object(notes_intake, "_call_vision_text", new=AsyncMock(return_value=vision_result)),
    ):
        result = await notes_intake.transcribe_note_image("/tmp/example.png", "caption", settings)

    assert result.text == "clean transcript"
    assert result.engine == "openai-codex:gpt-5.4"
    assert result.metadata["ocr_local_engine"] == "easyocr"
    assert result.metadata["ocr_local_engines_tried"] == ["glm_ocr", "easyocr"]
    assert "glm_ocr unavailable" in result.metadata["ocr_local_error"]
    assert result.metadata["ocr_effective_provider"] == "openai-codex"
