from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


Progress = Callable[[str], None]


@dataclass(frozen=True)
class OCRText:
    text: str
    label: str


def extract_first_frame_ocr(url: str, progress: Progress | None = None) -> OCRText | None:
    """Download a video, OCR its first decoded frame, and return overlay text if available."""
    if shutil.which("tesseract") is None:
        _emit(progress, "first-frame OCR skipped (tesseract not found)")
        return None

    label = "tesseract"
    started = time.monotonic()
    print(f"-> ocr / {label}", file=sys.stderr, flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="glance-ocr-") as temp_root:
            temp_dir = Path(temp_root)
            _emit(progress, "fetching video with yt-dlp for first-frame OCR")
            video_path = _download_video(url, temp_dir)
            _emit(progress, "extracting first frame with ffmpeg")
            frame_path = _extract_first_frame(video_path, temp_dir)
            _emit(progress, "running first-frame OCR with tesseract")
            text = _ocr_image(frame_path)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"  -> ocr failed: {exc}", file=sys.stderr, flush=True)
        _emit(progress, "first-frame OCR failed")
        return None

    if not text:
        elapsed = time.monotonic() - started
        print(f"  -> ocr returned no text in {elapsed:.2f}s", file=sys.stderr, flush=True)
        _emit(progress, "first-frame OCR returned no text")
        return None

    elapsed = time.monotonic() - started
    print(f"  -> ocr text {len(text)} chars in {elapsed:.2f}s", file=sys.stderr, flush=True)
    _emit(progress, "first-frame OCR ready")
    return OCRText(text=text, label=label)


def _emit(progress: Progress | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _download_video(url: str, temp_dir: Path) -> Path:
    output_template = str(temp_dir / "source.%(ext)s")
    result = subprocess.run(
        [
            "yt-dlp",
            "-f",
            "bestvideo[vcodec!=none]/best[vcodec!=none]",
            "--no-playlist",
            "--output",
            output_template,
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp video download failed: {result.stderr.strip()}")

    candidates = [
        path
        for path in temp_dir.iterdir()
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise RuntimeError("yt-dlp did not write a video file")
    return max(candidates, key=lambda path: path.stat().st_size)


def _extract_first_frame(video_path: Path, temp_dir: Path) -> Path:
    frame_path = temp_dir / "frame.png"
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(frame_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg first-frame extraction failed: {result.stderr.strip()}")
    if not frame_path.exists():
        raise RuntimeError("ffmpeg did not write a frame image")
    return frame_path


def _ocr_image(frame_path: Path) -> str | None:
    result = subprocess.run(
        ["tesseract", str(frame_path), "stdout", "--psm", "6"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"tesseract OCR failed: {result.stderr.strip()}")
    return _clean_text(result.stdout) or None


def _clean_text(value: str) -> str:
    return " ".join(value.split())
