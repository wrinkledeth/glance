import json
import unittest
from unittest.mock import Mock, patch

from glance.cli import detect_source
from glance.instagram import fetch_instagram


class SourceDetectionTests(unittest.TestCase):
    def test_detects_instagram(self) -> None:
        self.assertEqual(detect_source("https://www.instagram.com/reel/abc123/"), "instagram")
        self.assertEqual(detect_source("https://instagram.com/p/abc123/"), "instagram")


class InstagramFetchTests(unittest.TestCase):
    def test_fetch_instagram_includes_transcript_and_top_comments(self) -> None:
        info = {
            "title": "Video by creator",
            "channel": "creator",
            "description": "caption text",
            "comment_count": 3,
            "comments": [
                {"author": "low", "text": "lower ranked", "like_count": 1},
                {"author": "top", "text": "most liked", "like_count": 20},
                {"author": "none", "text": "no likes"},
            ],
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.instagram.subprocess.run", return_value=result) as run,
            patch("glance.instagram.extract_transcript_from_info", return_value="spoken words"),
        ):
            content = fetch_instagram("https://www.instagram.com/reel/abc123/")

        run.assert_called_once()
        self.assertIn("Source: Instagram", content)
        self.assertIn("Caption:\ncaption text", content)
        self.assertIn("Transcript:\nspoken words", content)
        self.assertIn("Top comments (3 shown of 3 reported):", content)
        self.assertLess(content.index("@top"), content.index("@low"))


if __name__ == "__main__":
    unittest.main()
