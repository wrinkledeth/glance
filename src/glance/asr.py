from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

DEFAULT_MODEL = "large-v3-turbo"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
DEFAULT_TIMEOUT = 180.0


@dataclass(frozen=True)
class ASRTranscript:
    text: str
    label: str


Progress = Callable[[str], None]


def transcribe_url(url: str, progress: Progress | None = None) -> ASRTranscript | None:
    """Download clip audio, normalize it, and transcribe it if ASR is enabled."""
    if not is_enabled():
        return None

    started = time.monotonic()
    label = _backend_label()
    print(f"→ asr / {label}", file=sys.stderr, flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="glance-asr-") as temp_root:
            temp_dir = Path(temp_root)
            _emit(progress, "fetching audio with yt-dlp")
            audio_path = _download_audio(url, temp_dir)
            _emit(progress, "normalizing audio with ffmpeg")
            wav_path = _normalize_audio(audio_path, temp_dir)
            _emit(progress, f"transcribing with {label}")
            transcript = _transcribe_wav(wav_path)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"  ↳ asr failed: {exc}", file=sys.stderr, flush=True)
        _emit(progress, "asr failed")
        return None

    if not transcript:
        elapsed = time.monotonic() - started
        print(f"  ↳ asr returned no transcript in {elapsed:.2f}s", file=sys.stderr, flush=True)
        _emit(progress, "asr returned no transcript")
        return None
    elapsed = time.monotonic() - started
    print(f"  ↳ asr transcript {len(transcript)} chars in {elapsed:.2f}s", file=sys.stderr, flush=True)
    _emit(progress, "asr transcript ready")
    return ASRTranscript(text=transcript, label=label)


def _emit(progress: Progress | None, message: str) -> None:
    if progress is not None:
        progress(message)


def is_enabled() -> bool:
    cmd = os.environ.get("GLANCE_ASR_CMD")
    if cmd and cmd.strip():
        return True
    return _env_flag("GLANCE_ASR_ENABLED")


def _download_audio(url: str, temp_dir: Path) -> Path:
    output_template = str(temp_dir / "source.%(ext)s")
    result = subprocess.run(
        [
            "yt-dlp",
            "-f",
            "bestaudio/best",
            "--no-playlist",
            "--output",
            output_template,
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp audio download failed: {result.stderr.strip()}")

    candidates = [
        path
        for path in temp_dir.iterdir()
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise RuntimeError("yt-dlp did not write an audio file")
    return max(candidates, key=lambda path: path.stat().st_size)


def _normalize_audio(audio_path: Path, temp_dir: Path) -> Path:
    wav_path = temp_dir / "audio.wav"
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-af",
            "highpass=f=80,lowpass=f=8000",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio normalization failed: {result.stderr.strip()}")
    if not wav_path.exists():
        raise RuntimeError("ffmpeg did not write normalized audio")
    return wav_path


def _transcribe_wav(wav_path: Path) -> str | None:
    try:
        result = subprocess.run(
            _transcribe_command(wav_path),
            capture_output=True,
            text=True,
            timeout=_timeout(),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    return _clean_transcript(result.stdout) or None


def _transcribe_command(wav_path: Path) -> list[str]:
    cmd_template = os.environ.get("GLANCE_ASR_CMD")
    if cmd_template and cmd_template.strip():
        return _custom_command(cmd_template, wav_path)

    return [
        sys.executable,
        "-m",
        "glance.asr",
        "_transcribe",
        str(wav_path),
        "--model",
        _model(),
        "--device",
        _device(),
        "--compute-type",
        _compute_type(),
    ]


def _custom_command(cmd_template: str, wav_path: Path) -> list[str]:
    command = shlex.split(cmd_template)
    if not command:
        raise ValueError("GLANCE_ASR_CMD is empty")

    audio = str(wav_path)
    has_placeholder = any("{audio}" in part for part in command)
    replaced = [part.replace("{audio}", audio) for part in command]
    if not has_placeholder:
        replaced.append(audio)
    return replaced


def _backend_label() -> str:
    cmd = os.environ.get("GLANCE_ASR_CMD")
    if cmd and cmd.strip():
        return "custom command"
    return f"faster-whisper {_model()}"


def _model() -> str:
    return os.environ.get("GLANCE_ASR_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _device() -> str:
    return os.environ.get("GLANCE_ASR_DEVICE", DEFAULT_DEVICE).strip() or DEFAULT_DEVICE


def _compute_type() -> str:
    value = os.environ.get("GLANCE_ASR_COMPUTE_TYPE", DEFAULT_COMPUTE_TYPE)
    return value.strip() or DEFAULT_COMPUTE_TYPE


def _timeout() -> float:
    raw = os.environ.get("GLANCE_ASR_TIMEOUT")
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT
    try:
        timeout = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    if timeout <= 0:
        return DEFAULT_TIMEOUT
    return timeout


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _clean_transcript(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return " ".join(" ".join(lines).split())


def _run_builtin_transcriber(audio_path: Path, model_name: str, device: str, compute_type: str) -> int:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper is not installed; run `uv sync --extra asr`", file=sys.stderr)
        return 2

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(
        str(audio_path),
        vad_filter=True,
        condition_on_previous_text=False,
    )
    for segment in segments:
        text = segment.text.strip()
        if text:
            print(text, flush=True)
    return 0


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m glance.asr")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe = subparsers.add_parser("_transcribe")
    transcribe.add_argument("audio", type=Path)
    transcribe.add_argument("--model", default=DEFAULT_MODEL)
    transcribe.add_argument("--device", default=DEFAULT_DEVICE)
    transcribe.add_argument("--compute-type", default=DEFAULT_COMPUTE_TYPE)

    args = parser.parse_args(argv)
    if args.command == "_transcribe":
        return _run_builtin_transcriber(args.audio, args.model, args.device, args.compute_type)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
