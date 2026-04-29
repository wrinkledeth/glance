import json
import unittest
from unittest.mock import Mock, patch

from glance.asr import ASRTranscript
from glance.cli import detect_source
from glance.instagram import fetch_instagram
from glance.ocr import OCRText
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
            patch("glance.instagram.extract_first_frame_ocr", return_value=None),
            patch("glance.instagram.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.instagram.transcribe_url") as transcribe_url,
        ):
            content = fetch_instagram("https://www.instagram.com/reel/abc123/")

        run.assert_called_once()
        transcribe_url.assert_not_called()
        self.assertIn("Source: Instagram", content)
        self.assertIn("Caption:\ncaption text", content)
        self.assertIn("Transcript:\nspoken words", content)
        self.assertIn("Top comments (3 shown of 3 reported):", content)
        self.assertLess(content.index("@top"), content.index("@low"))

    def test_fetch_instagram_includes_first_frame_ocr_when_available(self) -> None:
        info = {
            "title": "Video by creator",
            "channel": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.instagram.subprocess.run", return_value=result),
            patch(
                "glance.instagram.extract_first_frame_ocr",
                return_value=OCRText("overlay words", "tesseract"),
            ) as extract_ocr,
            patch("glance.instagram.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.instagram.transcribe_url"),
        ):
            content = fetch_instagram("https://www.instagram.com/reel/abc123/")

        extract_ocr.assert_called_once_with("https://www.instagram.com/reel/abc123/", progress=None)
        self.assertIn(
            "Overlay text (first-frame OCR: tesseract):\noverlay words",
            content,
        )
        self.assertLess(content.index("Caption:"), content.index("Overlay text"))
        self.assertLess(content.index("Overlay text"), content.index("Transcript:"))

    def test_fetch_instagram_omits_first_frame_ocr_when_unavailable(self) -> None:
        info = {
            "title": "Video by creator",
            "channel": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.instagram.subprocess.run", return_value=result),
            patch("glance.instagram.extract_first_frame_ocr", return_value=None),
            patch("glance.instagram.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.instagram.transcribe_url"),
        ):
            content = fetch_instagram("https://www.instagram.com/reel/abc123/")

        self.assertNotIn("Overlay text (first-frame OCR", content)

    def test_fetch_instagram_reports_metadata_and_subtitle_progress(self) -> None:
        info = {
            "title": "Video by creator",
            "channel": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")
        events: list[str] = []

        with (
            patch("glance.instagram.subprocess.run", return_value=result),
            patch("glance.instagram.extract_first_frame_ocr", return_value=None) as extract_ocr,
            patch("glance.instagram.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.instagram.transcribe_url") as transcribe_url,
        ):
            fetch_instagram("https://www.instagram.com/reel/abc123/", progress=events.append)

        transcribe_url.assert_not_called()
        args, kwargs = extract_ocr.call_args
        self.assertEqual(args, ("https://www.instagram.com/reel/abc123/",))
        self.assertIs(kwargs["progress"].__self__, events)
        self.assertEqual(
            events,
            [
                "fetching instagram metadata/comments with yt-dlp",
                "checking subtitles",
            ],
        )

    def test_fetch_instagram_uses_asr_when_subtitles_are_missing(self) -> None:
        info = {
            "title": "Video by creator",
            "channel": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.instagram.subprocess.run", return_value=result),
            patch("glance.instagram.extract_first_frame_ocr", return_value=None),
            patch("glance.instagram.extract_transcript_from_info", return_value=None),
            patch(
                "glance.instagram.transcribe_url",
                return_value=ASRTranscript("spoken words from asr", "faster-whisper large-v3-turbo"),
            ) as transcribe_url,
        ):
            content = fetch_instagram("https://www.instagram.com/reel/abc123/")

        transcribe_url.assert_called_once_with("https://www.instagram.com/reel/abc123/")
        self.assertIn(
            "Transcript (ASR: faster-whisper large-v3-turbo):\nspoken words from asr",
            content,
        )

    def test_fetch_instagram_passes_progress_to_asr(self) -> None:
        info = {"title": "Video by creator", "channel": "creator"}
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")
        events: list[str] = []
        url = "https://www.instagram.com/reel/abc123/"

        with (
            patch("glance.instagram.subprocess.run", return_value=result),
            patch("glance.instagram.extract_first_frame_ocr", return_value=None),
            patch("glance.instagram.extract_transcript_from_info", return_value=None),
            patch(
                "glance.instagram.transcribe_url",
                return_value=ASRTranscript("spoken words from asr", "faster-whisper large-v3-turbo"),
            ) as transcribe_url,
        ):
            fetch_instagram(url, progress=events.append)

        args, kwargs = transcribe_url.call_args
        self.assertEqual(args, (url,))
        self.assertIs(kwargs["progress"].__self__, events)
        self.assertEqual(events[:2], ["fetching instagram metadata/comments with yt-dlp", "checking subtitles"])

    def test_fetch_instagram_keeps_missing_marker_when_asr_fails(self) -> None:
        info = {"title": "Video by creator", "channel": "creator"}
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.instagram.subprocess.run", return_value=result),
            patch("glance.instagram.extract_first_frame_ocr", return_value=None),
            patch("glance.instagram.extract_transcript_from_info", return_value=None),
            patch("glance.instagram.transcribe_url", return_value=None) as transcribe_url,
        ):
            content = fetch_instagram("https://www.instagram.com/reel/abc123/")

        transcribe_url.assert_called_once_with("https://www.instagram.com/reel/abc123/")
        self.assertIn("Transcript:\n(no transcript/subtitles returned by yt-dlp)", content)


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
            patch("glance.tiktok.extract_first_frame_ocr", return_value=None),
            patch("glance.tiktok.extract_transcript_from_info", return_value=None),
            patch("glance.tiktok.transcribe_url", return_value=None) as transcribe_url,
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        run.assert_called_once()
        transcribe_url.assert_called_once_with("https://www.tiktok.com/@creator/video/abc123/")
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
            patch("glance.tiktok.extract_first_frame_ocr", return_value=None),
            patch("glance.tiktok.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.tiktok.transcribe_url") as transcribe_url,
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        transcribe_url.assert_not_called()
        self.assertIn("Transcript:\nspoken words", content)
        self.assertIn("Top comments (2 shown of 2 reported):", content)
        self.assertLess(content.index("@top"), content.index("@low"))

    def test_fetch_tiktok_includes_first_frame_ocr_when_available(self) -> None:
        info = {
            "title": "Video by creator",
            "uploader": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.tiktok.subprocess.run", return_value=result),
            patch(
                "glance.tiktok.extract_first_frame_ocr",
                return_value=OCRText("overlay words", "tesseract"),
            ) as extract_ocr,
            patch("glance.tiktok.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.tiktok.transcribe_url"),
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        extract_ocr.assert_called_once_with("https://www.tiktok.com/@creator/video/abc123/", progress=None)
        self.assertIn(
            "Overlay text (first-frame OCR: tesseract):\noverlay words",
            content,
        )
        self.assertLess(content.index("Caption:"), content.index("Overlay text"))
        self.assertLess(content.index("Overlay text"), content.index("Transcript:"))

    def test_fetch_tiktok_omits_first_frame_ocr_when_unavailable(self) -> None:
        info = {
            "title": "Video by creator",
            "uploader": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.tiktok.subprocess.run", return_value=result),
            patch("glance.tiktok.extract_first_frame_ocr", return_value=None),
            patch("glance.tiktok.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.tiktok.transcribe_url"),
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        self.assertNotIn("Overlay text (first-frame OCR", content)

    def test_fetch_tiktok_reports_metadata_and_subtitle_progress(self) -> None:
        info = {
            "title": "Video by creator",
            "uploader": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")
        events: list[str] = []

        with (
            patch("glance.tiktok.subprocess.run", return_value=result),
            patch("glance.tiktok.extract_first_frame_ocr", return_value=None) as extract_ocr,
            patch("glance.tiktok.extract_transcript_from_info", return_value="spoken words"),
            patch("glance.tiktok.transcribe_url") as transcribe_url,
        ):
            fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/", progress=events.append)

        transcribe_url.assert_not_called()
        args, kwargs = extract_ocr.call_args
        self.assertEqual(args, ("https://www.tiktok.com/@creator/video/abc123/",))
        self.assertIs(kwargs["progress"].__self__, events)
        self.assertEqual(
            events,
            [
                "fetching tiktok metadata/comments with yt-dlp",
                "checking subtitles",
            ],
        )

    def test_fetch_tiktok_uses_asr_when_subtitles_are_missing(self) -> None:
        info = {
            "title": "Video by creator",
            "uploader": "creator",
            "description": "caption text",
        }
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")

        with (
            patch("glance.tiktok.subprocess.run", return_value=result),
            patch("glance.tiktok.extract_first_frame_ocr", return_value=None),
            patch("glance.tiktok.extract_transcript_from_info", return_value=None),
            patch(
                "glance.tiktok.transcribe_url",
                return_value=ASRTranscript("spoken words from asr", "faster-whisper large-v3-turbo"),
            ) as transcribe_url,
        ):
            content = fetch_tiktok("https://www.tiktok.com/@creator/video/abc123/")

        transcribe_url.assert_called_once_with("https://www.tiktok.com/@creator/video/abc123/")
        self.assertIn(
            "Transcript (ASR: faster-whisper large-v3-turbo):\nspoken words from asr",
            content,
        )

    def test_fetch_tiktok_passes_progress_to_asr(self) -> None:
        info = {"title": "Video by creator", "uploader": "creator"}
        result = Mock(returncode=0, stdout=json.dumps(info), stderr="")
        events: list[str] = []
        url = "https://www.tiktok.com/@creator/video/abc123/"

        with (
            patch("glance.tiktok.subprocess.run", return_value=result),
            patch("glance.tiktok.extract_first_frame_ocr", return_value=None),
            patch("glance.tiktok.extract_transcript_from_info", return_value=None),
            patch(
                "glance.tiktok.transcribe_url",
                return_value=ASRTranscript("spoken words from asr", "faster-whisper large-v3-turbo"),
            ) as transcribe_url,
        ):
            fetch_tiktok(url, progress=events.append)

        args, kwargs = transcribe_url.call_args
        self.assertEqual(args, (url,))
        self.assertIs(kwargs["progress"].__self__, events)
        self.assertEqual(events[:2], ["fetching tiktok metadata/comments with yt-dlp", "checking subtitles"])


if __name__ == "__main__":
    unittest.main()
