import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from glance import asr


class ASRCommandTests(unittest.TestCase):
    def test_custom_command_replaces_audio_placeholder(self) -> None:
        with patch.dict(os.environ, {"GLANCE_ASR_CMD": "qwen-asr --input={audio} --plain"}, clear=True):
            command = asr._transcribe_command(Path("/tmp/audio file.wav"))

        self.assertEqual(command, ["qwen-asr", "--input=/tmp/audio file.wav", "--plain"])

    def test_custom_command_appends_audio_when_placeholder_is_missing(self) -> None:
        with patch.dict(os.environ, {"GLANCE_ASR_CMD": "whisper-cli --json"}, clear=True):
            command = asr._transcribe_command(Path("/tmp/audio.wav"))

        self.assertEqual(command, ["whisper-cli", "--json", "/tmp/audio.wav"])

    def test_builtin_command_uses_default_faster_whisper_knobs(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            command = asr._transcribe_command(Path("/tmp/audio.wav"))

        self.assertEqual(command[:4], [sys.executable, "-m", "glance.asr", "_transcribe"])
        self.assertIn("large-v3-turbo", command)
        self.assertIn("cuda", command)
        self.assertIn("float16", command)

    def test_transcribe_wav_returns_none_on_timeout(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"GLANCE_ASR_CMD": "asr-bin {audio}", "GLANCE_ASR_TIMEOUT": "7"},
                clear=True,
            ),
            patch(
                "glance.asr.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["asr-bin"], timeout=7),
            ) as run,
        ):
            transcript = asr._transcribe_wav(Path("/tmp/audio.wav"))

        self.assertIsNone(transcript)
        self.assertEqual(run.call_args.kwargs["timeout"], 7.0)


class ASRWorkflowTests(unittest.TestCase):
    def test_transcribe_url_cleans_temp_dir(self) -> None:
        seen: dict[str, Path] = {}

        def fake_download(_url: str, temp_dir: Path) -> Path:
            seen["temp_dir"] = temp_dir
            audio_path = temp_dir / "source.webm"
            audio_path.write_text("audio")
            return audio_path

        def fake_normalize(_audio_path: Path, temp_dir: Path) -> Path:
            wav_path = temp_dir / "audio.wav"
            wav_path.write_text("wav")
            return wav_path

        with (
            patch.dict(os.environ, {"GLANCE_ASR_ENABLED": "1"}, clear=True),
            patch("glance.asr._download_audio", side_effect=fake_download),
            patch("glance.asr._normalize_audio", side_effect=fake_normalize),
            patch("glance.asr._transcribe_wav", return_value="spoken words"),
        ):
            transcript = asr.transcribe_url("https://www.instagram.com/reel/abc123/")

        self.assertIsNotNone(transcript)
        assert transcript is not None
        self.assertEqual(transcript.text, "spoken words")
        self.assertEqual(transcript.label, "faster-whisper large-v3-turbo")
        self.assertFalse(seen["temp_dir"].exists())

    def test_transcribe_url_reports_success_progress(self) -> None:
        events: list[str] = []

        def fake_download(_url: str, temp_dir: Path) -> Path:
            audio_path = temp_dir / "source.webm"
            audio_path.write_text("audio")
            return audio_path

        def fake_normalize(_audio_path: Path, temp_dir: Path) -> Path:
            wav_path = temp_dir / "audio.wav"
            wav_path.write_text("wav")
            return wav_path

        with (
            patch.dict(os.environ, {"GLANCE_ASR_ENABLED": "1"}, clear=True),
            patch("glance.asr._download_audio", side_effect=fake_download),
            patch("glance.asr._normalize_audio", side_effect=fake_normalize),
            patch("glance.asr._transcribe_wav", return_value="spoken words"),
        ):
            transcript = asr.transcribe_url(
                "https://www.instagram.com/reel/abc123/",
                progress=events.append,
            )

        self.assertIsNotNone(transcript)
        self.assertEqual(
            events,
            [
                "fetching audio with yt-dlp",
                "normalizing audio with ffmpeg",
                "transcribing with faster-whisper large-v3-turbo",
                "asr transcript ready",
            ],
        )

    def test_transcribe_url_reports_failure_progress(self) -> None:
        events: list[str] = []

        with (
            patch.dict(os.environ, {"GLANCE_ASR_ENABLED": "1"}, clear=True),
            patch("glance.asr._download_audio", side_effect=RuntimeError("download failed")),
        ):
            transcript = asr.transcribe_url(
                "https://www.tiktok.com/@creator/video/abc123/",
                progress=events.append,
            )

        self.assertIsNone(transcript)
        self.assertEqual(events, ["fetching audio with yt-dlp", "asr failed"])

    def test_transcribe_url_returns_none_when_disabled(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("glance.asr._download_audio") as download_audio,
        ):
            transcript = asr.transcribe_url("https://www.tiktok.com/@creator/video/abc123/")

        self.assertIsNone(transcript)
        download_audio.assert_not_called()

    def test_download_audio_uses_ytdlp_and_returns_downloaded_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glance-asr-test-") as temp_root:
            temp_dir = Path(temp_root)

            def fake_run(command: list[str], **_kwargs: object) -> Mock:
                Path(command[command.index("--output") + 1].replace("%(ext)s", "webm")).write_text("audio")
                return Mock(returncode=0, stderr="")

            with patch("glance.asr.subprocess.run", side_effect=fake_run) as run:
                audio_path = asr._download_audio("https://www.tiktok.com/@creator/video/abc123/", temp_dir)

        self.assertEqual(audio_path.name, "source.webm")
        self.assertEqual(run.call_args.args[0][0], "yt-dlp")


if __name__ == "__main__":
    unittest.main()
