import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path

NOTES_GROUP_ID = "-1003960601334"
SESSIONS_JSON = Path.home() / ".hermes" / "sessions" / "sessions.json"
LOG_FILE = Path.home() / ".hermes" / "logs" / "notes_preprocessor.jsonl"
PREPROCESSOR_INSTRUCTIONS = Path.home() / ".hermes" / "agents" / "notes-intake" / "preprocessor-instructions.md"
MEDIA_ANALYSIS_MARKERS = (
    "[NOTES INBOX MEDIA ANALYSIS]",
    "capture_artifact_path:",
    "saved_media_path:",
    "ocr_transcript:",
    "audio_transcript:",
)
URL_RE = re.compile(r"https?://\S+", re.I)
_TRAILING_URL_PUNCT = ")]>,.;:'\""
_MAX_URLS = 10
_MAX_FETCH_BYTES = 250_000
_MAX_TEXT_EXCERPT = 1800


def _load_sessions() -> dict:
    if not SESSIONS_JSON.exists():
        return {}
    try:
        return json.loads(SESSIONS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_origin_by_session_id(session_id: str) -> dict | None:
    for entry in _load_sessions().values():
        if entry.get("session_id") == session_id:
            return entry.get("origin") or {}
    return None


def _classify_modality(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return "media-or-empty"
    if any(marker in stripped for marker in MEDIA_ANALYSIS_MARKERS):
        return "media"
    if URL_RE.search(stripped):
        return "link"
    return "text"


def _extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in URL_RE.findall(text or ""):
        url = raw.rstrip(_TRAILING_URL_PUNCT)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls[:_MAX_URLS]


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _strip_html_to_text(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html or "")
    cleaned = re.sub(r"(?is)<!--.*?-->", " ", cleaned)
    cleaned = re.sub(r"(?is)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?is)</(p|div|section|article|li|h1|h2|h3|h4|h5|h6)>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    lines = [_collapse_whitespace(line) for line in cleaned.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    if not match:
        return ""
    return _collapse_whitespace(unescape(match.group(1)))


def _extract_meta_description(html: str) -> str:
    patterns = (
        r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'(?is)<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        r'(?is)<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
        r'(?is)<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:description["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html or "")
        if match:
            return _collapse_whitespace(unescape(match.group(1)))
    return ""


def _decode_response_body(body: bytes, content_type_header: str) -> str:
    charset_match = re.search(r"charset=([\w\-]+)", content_type_header or "", re.I)
    encoding = charset_match.group(1) if charset_match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


def _is_youtube_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def _fetch_youtube_metadata(url: str) -> dict:
    """Fetch lightweight YouTube metadata without downloading/parsing video HTML.

    We intentionally do not fetch the watch page here: YouTube HTML is mostly JS
    config noise in a notes-intake context. Transcript extraction remains an
    explicit/on-demand workflow handled by the youtube-content skill.
    """
    endpoint = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": url, "format": "json"}
    )
    request = urllib.request.Request(
        endpoint,
        headers={
            "User-Agent": "HermesNotesPreprocessor/1.0 (+AnythingInbox)",
            "Accept": "application/json,*/*;q=0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read(_MAX_FETCH_BYTES)
    except urllib.error.HTTPError as exc:
        return {
            "url": url,
            "success": False,
            "source_type": "youtube_metadata",
            "error": f"youtube metadata unavailable: HTTP {exc.code}; generic video-page fetch skipped",
        }
    except Exception as exc:
        return {
            "url": url,
            "success": False,
            "source_type": "youtube_metadata",
            "error": f"youtube metadata unavailable: {exc}; generic video-page fetch skipped",
        }

    try:
        data = json.loads(_decode_response_body(body, content_type))
    except Exception as exc:
        return {
            "url": url,
            "success": False,
            "source_type": "youtube_metadata",
            "content_type": content_type,
            "error": f"youtube metadata unavailable: invalid JSON ({exc}); generic video-page fetch skipped",
        }

    title = _collapse_whitespace(str(data.get("title") or ""))
    channel_name = _collapse_whitespace(str(data.get("author_name") or ""))
    if not (title or channel_name):
        return {
            "url": url,
            "success": False,
            "source_type": "youtube_metadata",
            "content_type": content_type,
            "error": "youtube metadata unavailable: empty oEmbed response; generic video-page fetch skipped",
        }

    return {
        "url": url,
        "success": True,
        "source_type": "youtube_metadata",
        "content_type": content_type or "application/json",
        "title": title,
        "channel_name": channel_name,
        "channel_url": str(data.get("author_url") or ""),
        "provider_name": str(data.get("provider_name") or "YouTube"),
        "provider_url": str(data.get("provider_url") or "https://www.youtube.com/"),
        "thumbnail_url": str(data.get("thumbnail_url") or ""),
    }


def _fetch_url_preview(url: str) -> dict:
    if _is_youtube_url(url):
        return _fetch_youtube_metadata(url)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesNotesPreprocessor/1.0 (+AnythingInbox)",
            "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read(_MAX_FETCH_BYTES)
    except urllib.error.HTTPError as exc:
        return {"url": url, "success": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"url": url, "success": False, "error": str(exc)}

    text = _decode_response_body(body, content_type)
    lowered_type = (content_type or "").lower()
    if "html" in lowered_type or not lowered_type:
        title = _extract_title(text)
        description = _extract_meta_description(text)
        visible_text = _strip_html_to_text(text)
        excerpt = visible_text[:_MAX_TEXT_EXCERPT].strip()
        if not (title or description or excerpt):
            return {
                "url": url,
                "success": False,
                "content_type": content_type,
                "error": "no readable page content extracted",
            }
        return {
            "url": url,
            "success": True,
            "content_type": content_type or "text/html",
            "title": title,
            "description": description,
            "text_excerpt": excerpt,
        }

    if lowered_type.startswith("text/") or "json" in lowered_type or "xml" in lowered_type:
        excerpt = _collapse_whitespace(text)[:_MAX_TEXT_EXCERPT]
        if not excerpt:
            return {
                "url": url,
                "success": False,
                "content_type": content_type,
                "error": "empty textual response",
            }
        return {
            "url": url,
            "success": True,
            "content_type": content_type,
            "title": "",
            "description": "",
            "text_excerpt": excerpt,
        }

    return {
        "url": url,
        "success": False,
        "content_type": content_type,
        "error": f"unsupported content type: {content_type}",
    }


def _log(payload: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load_preprocessor_instructions() -> list[str]:
    try:
        text = PREPROCESSOR_INSTRUCTIONS.read_text(encoding="utf-8")
    except Exception:
        text = """handling_instructions:
- This Telegram group is an intake surface, not a normal conversational surface.
- Treat the original message as raw capture.
- Follow the file-defined notes-intake agent behavior under ~/.hermes/agents/notes-intake/ and ~/.hermes/skills/.
"""
    return text.rstrip().splitlines()


def _build_context(origin: dict, text: str) -> str:
    modality = _classify_modality(text)
    urls = _extract_urls(text)
    prefetched = [_fetch_url_preview(url) for url in urls]
    payload = {
        "ts": datetime.now().isoformat(),
        "chat_id": origin.get("chat_id"),
        "chat_name": origin.get("chat_name"),
        "modality": modality,
        "has_url": bool(urls),
        "urls": urls,
        "prefetched_ok": sum(1 for item in prefetched if item.get("success")),
        "prefetched_failed": sum(1 for item in prefetched if not item.get("success")),
        "raw_preview": (text or "")[:400],
    }
    _log(payload)

    lines = [
        "[NOTES INBOX PREPROCESSOR OUTPUT]",
        f"source_chat: {origin.get('chat_name') or 'unknown'}",
        f"source_chat_id: {origin.get('chat_id') or 'unknown'}",
        f"capture_modality: {modality}",
        "preprocessor_rule: preserve raw input first, then route/index",
    ]

    if prefetched:
        lines.append("prefetched_urls:")
        for item in prefetched:
            lines.append(f"- url: {item.get('url', '')}")
            if item.get("success"):
                lines.append("  fetch_status: ok")
                if item.get("source_type"):
                    lines.append(f"  source_type: {item.get('source_type')}")
                if item.get("content_type"):
                    lines.append(f"  content_type: {item.get('content_type')}")
                if item.get("title"):
                    lines.append(f"  title: {item.get('title')}")
                if item.get("channel_name"):
                    lines.append(f"  channel_name: {item.get('channel_name')}")
                if item.get("channel_url"):
                    lines.append(f"  channel_url: {item.get('channel_url')}")
                if item.get("provider_name"):
                    lines.append(f"  provider_name: {item.get('provider_name')}")
                if item.get("provider_url"):
                    lines.append(f"  provider_url: {item.get('provider_url')}")
                if item.get("thumbnail_url"):
                    lines.append(f"  thumbnail_url: {item.get('thumbnail_url')}")
                if item.get("description"):
                    lines.append(f"  description: {item.get('description')}")
                if item.get("text_excerpt"):
                    lines.append("  extracted_text:")
                    for excerpt_line in str(item.get("text_excerpt") or "").splitlines():
                        lines.append(f"    {excerpt_line}")
            else:
                lines.append("  fetch_status: failed")
                if item.get("source_type"):
                    lines.append(f"  source_type: {item.get('source_type')}")
                if item.get("content_type"):
                    lines.append(f"  content_type: {item.get('content_type')}")
                lines.append(f"  fetch_error: {item.get('error') or 'unknown error'}")

    lines.extend(_load_preprocessor_instructions())
    return "\n".join(lines)


def _pre_llm_call(session_id: str, user_message: str, platform: str, **kwargs):
    if platform != "telegram":
        return None
    origin = _find_origin_by_session_id(session_id)
    if not origin:
        return None
    if str(origin.get("chat_id", "")) != NOTES_GROUP_ID:
        return None
    return {"context": _build_context(origin, user_message or "")}


def register(ctx):
    ctx.register_hook("pre_llm_call", _pre_llm_call)
