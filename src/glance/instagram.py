import json
import subprocess
from datetime import datetime, timezone
from html import unescape
from typing import Any, Callable

from glance.asr import transcribe_url
from glance.youtube import extract_transcript_from_info

MAX_COMMENTS = 25
Progress = Callable[[str], None]


def fetch_instagram(url: str, progress: Progress | None = None) -> str:
    """Fetch an Instagram clip and return structured text for summarization."""
    _emit(progress, "fetching instagram metadata/comments with yt-dlp")
    info = _dump_info(url)

    parts: list[str] = ["Source: Instagram"]
    parts.extend(_metadata_lines(info))

    caption = _first_text(info, "description", "caption")
    if caption:
        parts.append(f"\nCaption:\n{caption}")

    _emit(progress, "checking subtitles")
    transcript = _extract_transcript(info)
    if transcript:
        parts.append(f"\nTranscript:\n{transcript}")
    else:
        if progress is None:
            asr_transcript = transcribe_url(url)
        else:
            asr_transcript = transcribe_url(url, progress=progress)
        if asr_transcript:
            parts.append(f"\nTranscript (ASR: {asr_transcript.label}):\n{asr_transcript.text}")
        else:
            parts.append("\nTranscript:\n(no transcript/subtitles returned by yt-dlp)")

    comments = _top_comments(info)
    reported_count = _first_int(info, "comment_count")
    if comments:
        total = max(reported_count or 0, len(comments))
        parts.append(f"\nTop comments ({min(len(comments), MAX_COMMENTS)} shown of {total} reported):")
        parts.extend(_format_comment(c) for c in comments[:MAX_COMMENTS])
    elif reported_count:
        parts.append(f"\nComments:\n({reported_count} comments reported, but yt-dlp returned no comment text)")
    else:
        parts.append("\nComments:\n(no comments returned by yt-dlp)")

    return "\n".join(parts).strip()


def _emit(progress: Progress | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _dump_info(url: str) -> dict[str, Any]:
    result = subprocess.run(
        ["yt-dlp", "--dump-single-json", "--no-download", "--write-comments", url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("yt-dlp returned invalid JSON") from exc
    if not isinstance(info, dict):
        raise RuntimeError("yt-dlp returned unexpected JSON")
    return info


def _metadata_lines(info: dict[str, Any]) -> list[str]:
    lines = []
    title = _first_text(info, "title", "fulltitle")
    if title:
        lines.append(f"Title: {title}")

    author = _first_text(info, "channel", "uploader_id")
    if author:
        if not author.startswith("@"):
            author = f"@{author}"
        lines.append(f"Author: {author}")
    else:
        author = _first_text(info, "uploader")
        if author:
            lines.append(f"Author: {author}")

    published = _format_timestamp(_first_int(info, "timestamp"))
    if published:
        lines.append(f"Posted: {published}")

    duration = info.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        lines.append(f"Duration: {duration:g}s")

    like_count = _first_int(info, "like_count")
    if like_count is not None:
        lines.append(f"Likes: {like_count}")

    comment_count = _first_int(info, "comment_count")
    if comment_count is not None:
        lines.append(f"Comments reported: {comment_count}")

    return lines


def _extract_transcript(info: dict[str, Any]) -> str | None:
    chunks = []
    transcript = extract_transcript_from_info(info)
    if transcript:
        chunks.append(_clean_text(transcript))

    entries = _entries(info)
    for index, entry in enumerate(entries, 1):
        transcript = extract_transcript_from_info(entry)
        if not transcript:
            continue
        cleaned = _clean_text(transcript)
        if len(entries) > 1:
            chunks.append(f"[Clip {index}] {cleaned}")
        else:
            chunks.append(cleaned)

    return "\n\n".join(chunk for chunk in chunks if chunk) or None


def _top_comments(info: dict[str, Any]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    seen = set()
    for source in [info, *_entries(info)]:
        raw_comments = source.get("comments")
        if not isinstance(raw_comments, list):
            continue
        for comment in raw_comments:
            if not isinstance(comment, dict):
                continue
            text = _clean_text(comment.get("text"))
            if not text:
                continue
            key = (comment.get("id"), comment.get("author"), text)
            if key in seen:
                continue
            seen.add(key)
            comments.append({**comment, "text": text})

    if any(isinstance(c.get("like_count"), int) for c in comments):
        comments.sort(
            key=lambda c: (
                c.get("like_count") if isinstance(c.get("like_count"), int) else -1,
                c.get("timestamp") if isinstance(c.get("timestamp"), int) else 0,
            ),
            reverse=True,
        )
    return comments


def _format_comment(comment: dict[str, Any]) -> str:
    author = _clean_text(comment.get("author") or comment.get("author_id")) or "unknown"
    if author != "unknown" and not author.startswith("@"):
        author = f"@{author}"

    details = [author]
    like_count = comment.get("like_count")
    if isinstance(like_count, int):
        details.append(f"{like_count} likes")

    return f"[{', '.join(details)}] {comment['text']}"


def _entries(info: dict[str, Any]) -> list[dict[str, Any]]:
    entries = info.get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _first_text(info: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        cleaned = _clean_text(info.get(key))
        if cleaned:
            return cleaned
    for entry in _entries(info):
        for key in keys:
            cleaned = _clean_text(entry.get(key))
            if cleaned:
                return cleaned
    return None


def _first_int(info: dict[str, Any], *keys: str) -> int | None:
    for source in [info, *_entries(info)]:
        for key in keys:
            value = source.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unescape(str(value)).replace("\r", "\n")
    return " ".join(text.split())


def _format_timestamp(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
