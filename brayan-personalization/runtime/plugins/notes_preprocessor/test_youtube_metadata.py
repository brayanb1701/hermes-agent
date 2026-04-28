import importlib.util
import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("__init__.py")
spec = importlib.util.spec_from_file_location("notes_preprocessor", MODULE_PATH)
notes_preprocessor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes_preprocessor)


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json"):
        self._body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _max_bytes):
        return self._body


class YouTubeMetadataTests(unittest.TestCase):
    def test_youtube_url_uses_oembed_metadata_not_generic_html_prefetch(self):
        requested_urls = []

        def fake_urlopen(request, timeout=8):
            requested_urls.append(request.full_url)
            self.assertIn("youtube.com/oembed", request.full_url)
            payload = {
                "title": "The Video Title",
                "author_name": "Useful Channel",
                "author_url": "https://www.youtube.com/@useful",
                "provider_name": "YouTube",
                "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            }
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        with patch.object(notes_preprocessor.urllib.request, "urlopen", fake_urlopen):
            result = notes_preprocessor._fetch_url_preview("https://youtu.be/dQw4w9WgXcQ")

        self.assertTrue(result["success"])
        self.assertEqual(result["source_type"], "youtube_metadata")
        self.assertEqual(result["title"], "The Video Title")
        self.assertEqual(result["channel_name"], "Useful Channel")
        self.assertEqual(result["provider_name"], "YouTube")
        self.assertTrue(result["thumbnail_url"].startswith("https://i.ytimg.com/"))
        self.assertNotIn("text_excerpt", result)
        self.assertTrue(requested_urls)
        self.assertTrue(all("youtu.be/dQw4w9WgXcQ" not in url.split("url=", 1)[0] for url in requested_urls))

    def test_youtube_metadata_failure_does_not_fetch_original_video_page(self):
        requested_urls = []

        def fake_urlopen(request, timeout=8):
            requested_urls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 404, "not found", hdrs=None, fp=None)

        with patch.object(notes_preprocessor.urllib.request, "urlopen", fake_urlopen):
            result = notes_preprocessor._fetch_url_preview("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertFalse(result["success"])
        self.assertEqual(result["source_type"], "youtube_metadata")
        self.assertIn("metadata unavailable", result["error"])
        self.assertTrue(requested_urls)
        self.assertTrue(all("watch?v=dQw4w9WgXcQ" not in url.split("url=", 1)[0] for url in requested_urls))


if __name__ == "__main__":
    unittest.main()
