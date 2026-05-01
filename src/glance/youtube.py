import json
import subprocess
from typing import Callable

import httpx

Progress = Callable[[str], None]


def extract_transcript(url: str, progress: Progress | None = None) -> str:
    """Extract transcript from a YouTube video using yt-dlp, falling back to Whisper ASR."""
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    info = json.loads(result.stdout)

    transcript = extract_transcript_from_info(info)
    if transcript:
        return transcript

    from glance import asr
    if asr.is_enabled():
        _emit(progress, "no subtitles found, transcribing audio with whisper")
        result = asr.transcribe_url(url, progress=progress)
        if result:
            return result.text

    raise RuntimeError("No English subtitles found for this video.")


def _emit(progress: Progress | None, message: str) -> None:
    if progress is not None:
        progress(message)


def extract_transcript_from_info(info: dict) -> str | None:
    """Extract English subtitle text from a yt-dlp info dict, if available."""
    # Try manual subtitles first, then auto-generated.
    for sub_key in ("subtitles", "automatic_captions"):
        for fmt in _english_subtitle_formats(info.get(sub_key, {})):
            if fmt.get("ext") == "json3" and fmt.get("url"):
                return _fetch_json3_transcript(fmt["url"])

    # Fallback: first available English subtitle format.
    for sub_key in ("subtitles", "automatic_captions"):
        for fmt in _english_subtitle_formats(info.get(sub_key, {})):
            if fmt.get("url"):
                return _fetch_vtt_transcript(fmt["url"])

    return None


def _english_subtitle_formats(subtitles: dict) -> list[dict]:
    """Return English subtitle formats, preferring plain `en` tracks."""
    if not isinstance(subtitles, dict):
        return []

    langs = []
    for lang in subtitles:
        normalized = lang.lower().replace("_", "-")
        if normalized == "en":
            langs.insert(0, lang)
        elif normalized.startswith("en-"):
            langs.append(lang)

    formats: list[dict] = []
    for lang in langs:
        tracks = subtitles.get(lang) or []
        if isinstance(tracks, list):
            formats.extend(fmt for fmt in tracks if isinstance(fmt, dict))
    return formats


def _fetch_json3_transcript(url: str) -> str:
    """Fetch and parse a json3 subtitle file into plain text."""
    resp = httpx.get(url, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()

    segments = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if segs:
            text = "".join(s.get("utf8", "") for s in segs).strip()
            if text and text != "\n":
                segments.append(text)

    return " ".join(segments)


def _fetch_vtt_transcript(url: str) -> str:
    """Fetch a VTT subtitle file and extract plain text."""
    resp = httpx.get(url, follow_redirects=True)
    resp.raise_for_status()

    lines = []
    for line in resp.text.splitlines():
        if line.startswith("WEBVTT") or "-->" in line or not line.strip():
            continue
        if line.strip().isdigit():
            continue
        lines.append(line.strip())

    # Deduplicate consecutive identical lines (common in auto-subs)
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    return " ".join(deduped)
