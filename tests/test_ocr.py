import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

from glance import ocr


class OCRWorkflowTests(unittest.TestCase):
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
            raise AssertionError(f"unexpected command: {command}")

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"response": "  overlay\n\n words  \n"}

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("glance.ocr.subprocess.run", side_effect=fake_run) as run,
            patch("glance.ocr.httpx.post", return_value=response) as post,
        ):
            result = ocr.extract_first_frame_ocr(
                "https://www.tiktok.com/@creator/video/abc123/",
                progress=events.append,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.text, "overlay words")
        self.assertEqual(result.label, "ollama/gemma4:e4b")
        self.assertEqual([call.args[0][0] for call in run.call_args_list], ["yt-dlp", "ffmpeg"])
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/generate")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gemma4:e4b")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["think"], False)
        self.assertEqual(len(payload["images"]), 1)
        self.assertEqual(
            events,
            [
                "fetching video with yt-dlp for first-frame OCR",
                "extracting first frame with ffmpeg",
                "running first-frame OCR with ollama/gemma4:e4b",
                "OCR: overlay words",
            ],
        )

    def test_extract_first_frame_ocr_returns_none_on_stage_failure(self) -> None:
        for failing_stage in ("yt-dlp", "ffmpeg", "ollama"):
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
                    raise AssertionError(f"unexpected command: {command}")

                response = Mock()
                response.raise_for_status.return_value = None
                response.json.return_value = {"response": "overlay"}

                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch("glance.ocr.subprocess.run", side_effect=fake_run),
                    patch(
                        "glance.ocr.httpx.post",
                        side_effect=httpx.ConnectError("ollama unavailable")
                        if failing_stage == "ollama"
                        else None,
                        return_value=response,
                    ),
                ):
                    result = ocr.extract_first_frame_ocr(
                        "https://www.instagram.com/reel/abc123/",
                        progress=events.append,
                    )

                self.assertIsNone(result)
                self.assertEqual(events[-1], "first-frame OCR failed")

    def test_extract_first_frame_ocr_returns_none_on_empty_model_response(self) -> None:
        events: list[str] = []

        def fake_run(command: list[str], **_kwargs: object) -> Mock:
            if command[0] == "yt-dlp":
                output_template = command[command.index("--output") + 1]
                Path(output_template.replace("%(ext)s", "mp4")).write_text("video")
                return Mock(returncode=0, stdout="", stderr="")
            if command[0] == "ffmpeg":
                Path(command[-1]).write_text("frame")
                return Mock(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"response": " \n\t "}

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("glance.ocr.subprocess.run", side_effect=fake_run),
            patch("glance.ocr.httpx.post", return_value=response),
        ):
            result = ocr.extract_first_frame_ocr(
                "https://www.instagram.com/reel/abc123/",
                progress=events.append,
            )

        self.assertIsNone(result)
        self.assertEqual(events[-1], "first-frame OCR returned no text")
        self.assertNotIn("OCR:", "\n".join(events))

    def test_ocr_host_and_model_are_configurable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OLLAMA_HOST": "http://ollama-host:11434",
                "GLANCE_OCR_HOST": "http://vision-host:11434",
                "GLANCE_OCR_MODEL": "vision-test",
            },
            clear=True,
        ):
            self.assertEqual(ocr._ocr_host(), "http://vision-host:11434")
            self.assertEqual(ocr._ocr_model(), "vision-test")


if __name__ == "__main__":
    unittest.main()
