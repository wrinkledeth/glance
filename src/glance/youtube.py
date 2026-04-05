import json
import subprocess

import httpx


def extract_transcript(url: str) -> str:
    """Extract transcript from a YouTube video using yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    info = json.loads(result.stdout)

    # Try manual subtitles first, then auto-generated
    for sub_key in ("subtitles", "automatic_captions"):
        subs = info.get(sub_key, {})
        if "en" in subs:
            for fmt in subs["en"]:
                if fmt.get("ext") == "json3":
                    return _fetch_json3_transcript(fmt["url"])

    # Fallback: first available English subtitle format
    for sub_key in ("subtitles", "automatic_captions"):
        subs = info.get(sub_key, {})
        if "en" in subs and subs["en"]:
            return _fetch_vtt_transcript(subs["en"][0]["url"])

    raise RuntimeError("No English subtitles found for this video.")


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
