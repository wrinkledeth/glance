from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx


Progress = Callable[[str], None]
DEFAULT_OCR_MODEL = "gemma4:e4b"
DEFAULT_OCR_HOST = "http://localhost:11434"
OCR_PROMPT = (
    "Read all visible text in this image. Return only the exact text, preserving "
    "wording, punctuation, capitalization, and line order. Do not describe the "
    "image. Do not add commentary. If there is no readable text, return an empty "
    "string."
)


@dataclass(frozen=True)
class OCRText:
    text: str
    label: str


def extract_first_frame_ocr(url: str, progress: Progress | None = None) -> OCRText | None:
    """Download a video, OCR its first decoded frame, and return overlay text if available."""
    model = _ocr_model()
    label = f"ollama/{model}"
    started = time.monotonic()
    print(f"-> ocr / {label}", file=sys.stderr, flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="glance-ocr-") as temp_root:
            temp_dir = Path(temp_root)
            _emit(progress, "fetching video with yt-dlp for first-frame OCR")
            video_path = _download_video(url, temp_dir)
            _emit(progress, "extracting first frame with ffmpeg")
            frame_path = _extract_first_frame(video_path, temp_dir)
            _emit(progress, f"running first-frame OCR with {label}")
            text = _ocr_image(frame_path, model=model)
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
        httpx.HTTPError,
    ) as exc:
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
    _emit(progress, f"OCR: {text}")
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


def _ocr_image(frame_path: Path, *, model: str) -> str | None:
    image = base64.b64encode(frame_path.read_bytes()).decode("ascii")
    resp = httpx.post(
        f"{_ocr_host().rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": OCR_PROMPT,
            "images": [image],
            "stream": False,
            "think": False,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Ollama OCR response was not an object")
    response = data.get("response")
    if not isinstance(response, str):
        raise ValueError("Ollama OCR response did not include text")
    return _clean_text(response) or None


def _ocr_model() -> str:
    return os.environ.get("GLANCE_OCR_MODEL", DEFAULT_OCR_MODEL).strip() or DEFAULT_OCR_MODEL


def _ocr_host() -> str:
    host = os.environ.get("GLANCE_OCR_HOST") or os.environ.get("OLLAMA_HOST") or DEFAULT_OCR_HOST
    return host.strip() or DEFAULT_OCR_HOST


def _clean_text(value: str) -> str:
    return " ".join(value.split())
