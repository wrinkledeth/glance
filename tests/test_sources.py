import json
import unittest
from unittest.mock import Mock, patch

from glance.cli import detect_source
from glance.instagram import fetch_instagram
from glance.tiktok import fetch_tiktok


class SourceDetectionTests(unittest.TestCase):
    def test_detects_instagram(self) -> None:
        self.assertEqual(detect_source("https://www.instagram.com/reel/abc123/"), "instagram")
        self.assertEqual(detect_source("https://instagram.com/p/abc123/"), "instagram")

    def test_detects_tiktok(self) -> None:
        self.assertEqual(
            detect_source("https://www.tiktok.com/@creator/video/7633073542514642206"),
            "tiktok",
        )
        self.assertEqual(detect_source("https://vm.tiktok.com/abc123/"), "tiktok")


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


class TikTokFetchTests(unittest.TestCase):
    def test_fetch_tiktok_includes_metadata_and_missing_transcript_marker(self) -> None:
        info = {
            "title": "Mixed Doubles Strategy",
            "channel": "creator",
            "description": "caption text",
            "duration": 50,
            "like_count": 494,
            "comment_count": 5,
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.tiktok.subprocess.run", return_value=result) as run,
            patch("glance.tiktok.extract_transcript_from_info", return_value=None),
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        run.assert_called_once()
        self.assertIn("Source: TikTok", content)
        self.assertIn("Title: Mixed Doubles Strategy", content)
        self.assertIn("Author: @creator", content)
        self.assertIn("Duration: 50s", content)
        self.assertIn("Likes: 494", content)
        self.assertIn("Caption:\ncaption text", content)
        self.assertIn("Transcript:\n(no transcript/subtitles returned by yt-dlp)", content)
        self.assertIn("Comments:\n(5 comments reported, but yt-dlp returned no comment text)", content)

    def test_fetch_tiktok_includes_transcript_and_top_comments(self) -> None:
        info = {
            "title": "Video by creator",
            "uploader": "creator",
            "description": "caption text",
            "comment_count": 2,
            "comments": [
                {"author": "low", "text": "lower ranked", "like_count": 1},
                {"author": "top", "text": "most liked", "like_count": 20},
            ],
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.tiktok.subprocess.run", return_value=result),
            patch("glance.tiktok.extract_transcript_from_info", return_value="spoken words"),
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        self.assertIn("Transcript:\nspoken words", content)
        self.assertIn("Top comments (2 shown of 2 reported):", content)
        self.assertLess(content.index("@top"), content.index("@low"))


if __name__ == "__main__":
    unittest.main()
