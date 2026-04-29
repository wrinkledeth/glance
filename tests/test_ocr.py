import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from glance import ocr


class OCRWorkflowTests(unittest.TestCase):
    def test_extract_first_frame_ocr_skips_when_tesseract_is_missing(self) -> None:
        events: list[str] = []

        with (
            patch("glance.ocr.shutil.which", return_value=None),
            patch("glance.ocr.subprocess.run") as run,
        ):
            result = ocr.extract_first_frame_ocr("https://www.instagram.com/reel/abc123/", progress=events.append)

        self.assertIsNone(result)
        run.assert_not_called()
        self.assertEqual(events, ["first-frame OCR skipped (tesseract not found)"])

    def test_extract_first_frame_ocr_returns_cleaned_text_on_success(self) -> None:
        events: list[str] = []

        def fake_run(command: list[str], **_kwargs: object) -> Mock:
            if command[0] == "yt-dlp":
                output_template = command[command.index("--output") + 1]
                Path(output_template.replace("%(ext)s", "mp4")).write_text("video")
                return Mock(returncode=0, stdout="", stderr="")
            if command[0] == "ffmpeg":
                Path(command[-1]).write_text("frame")
                return Mock(returncode=0, stdout="", stderr="")
            if command[0] == "tesseract":
                return Mock(returncode=0, stdout="  TOP LINE\n\n bottom   line  \n", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        with (
            patch("glance.ocr.shutil.which", return_value="/usr/bin/tesseract"),
            patch("glance.ocr.subprocess.run", side_effect=fake_run) as run,
        ):
            result = ocr.extract_first_frame_ocr("https://www.tiktok.com/@creator/video/abc123/", progress=events.append)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.text, "TOP LINE bottom line")
        self.assertEqual(result.label, "tesseract")
        self.assertEqual(run.call_args_list[-1].args[0][0], "tesseract")
        self.assertEqual(
            events,
            [
                "fetching video with yt-dlp for first-frame OCR",
                "extracting first frame with ffmpeg",
                "running first-frame OCR with tesseract",
                "first-frame OCR ready",
            ],
        )

    def test_extract_first_frame_ocr_returns_none_on_stage_failure(self) -> None:
        for failing_stage in ("yt-dlp", "ffmpeg", "tesseract"):
            with self.subTest(failing_stage=failing_stage):
                events: list[str] = []

                def fake_run(command: list[str], **_kwargs: object) -> Mock:
                    if command[0] == "yt-dlp":
                        if failing_stage == "yt-dlp":
                            return Mock(returncode=1, stdout="", stderr="download failed")
                        output_template = command[command.index("--output") + 1]
                        Path(output_template.replace("%(ext)s", "mp4")).write_text("video")
                        return Mock(returncode=0, stdout="", stderr="")
                    if command[0] == "ffmpeg":
                        if failing_stage == "ffmpeg":
                            return Mock(returncode=1, stdout="", stderr="frame failed")
                        Path(command[-1]).write_text("frame")
                        return Mock(returncode=0, stdout="", stderr="")
                    if command[0] == "tesseract":
                        if failing_stage == "tesseract":
                            return Mock(returncode=1, stdout="", stderr="ocr failed")
                        return Mock(returncode=0, stdout="overlay", stderr="")
                    raise AssertionError(f"unexpected command: {command}")

                with (
                    patch("glance.ocr.shutil.which", return_value="/usr/bin/tesseract"),
                    patch("glance.ocr.subprocess.run", side_effect=fake_run),
                ):
                    result = ocr.extract_first_frame_ocr(
                        "https://www.instagram.com/reel/abc123/",
                        progress=events.append,
                    )

                self.assertIsNone(result)
                self.assertEqual(events[-1], "first-frame OCR failed")


if __name__ == "__main__":
    unittest.main()
