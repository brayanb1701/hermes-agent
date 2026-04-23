import importlib.util
from pathlib import Path


def _load_module():
    plugin_path = Path.home() / ".hermes" / "plugins" / "notes_preprocessor" / "__init__.py"
    spec = importlib.util.spec_from_file_location("notes_preprocessor_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_notes_preprocessor_treats_media_analysis_blocks_as_media():
    module = _load_module()

    text = """[NOTES INBOX MEDIA ANALYSIS]
saved_media_path: /tmp/photo.png
capture_artifact_path: /tmp/ocr.md
ocr_transcript:
hello world
[END NOTES INBOX MEDIA ANALYSIS]"""
    assert module._classify_modality(text) == "media"


def test_notes_preprocessor_build_context_prefetches_urls_without_regex_routing(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_fetch_url_preview",
        lambda url: {
            "url": url,
            "success": True,
            "content_type": "text/html",
            "title": "Example title",
            "description": "Example description",
            "text_excerpt": "Useful extracted page text.",
        },
    )

    context = module._build_context(
        {"chat_id": "test-notes-chat", "chat_name": "Anything Inbox"},
        "Check this out https://example.com/post",
    )

    assert "capture_modality: link" in context
    assert "prefetched_urls:" in context
    assert "url: https://example.com/post" in context
    assert "fetch_status: ok" in context
    assert "title: Example title" in context
    assert "Useful extracted page text." in context
    assert "intent_label:" not in context
    assert "suggested_targets:" not in context
    assert "agent decides final organization" in context


def test_notes_preprocessor_build_context_reports_url_fetch_failure(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_fetch_url_preview",
        lambda url: {
            "url": url,
            "success": False,
            "error": "timeout",
        },
    )

    context = module._build_context(
        {"chat_id": "test-notes-chat", "chat_name": "Anything Inbox"},
        "https://example.com/fail",
    )

    assert "fetch_status: failed" in context
    assert "fetch_error: timeout" in context
    assert "If URL prefetch failed, use the original URL" in context


def test_notes_preprocessor_prefetches_multiple_related_urls(monkeypatch):
    module = _load_module()
    seen = []

    def fake_fetch(url):
        seen.append(url)
        return {
            "url": url,
            "success": True,
            "content_type": "text/html",
            "title": f"Title for {url}",
            "description": "",
            "text_excerpt": "excerpt",
        }

    monkeypatch.setattr(module, "_fetch_url_preview", fake_fetch)
    text = "Related: https://a.example/x https://b.example/y https://c.example/z https://d.example/q"

    context = module._build_context(
        {"chat_id": "test-notes-chat", "chat_name": "Anything Inbox"},
        text,
    )

    assert seen == [
        "https://a.example/x",
        "https://b.example/y",
        "https://c.example/z",
        "https://d.example/q",
    ]
    assert context.count("- url: https://") == 4
    assert "multiple URLs" in context