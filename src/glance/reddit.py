import json
from urllib.parse import urlparse, urlunparse

import httpx


USER_AGENT = "glance-cli/0.1"


def fetch_thread(url: str) -> str:
    """Fetch a Reddit thread and return structured text for summarization."""
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        thread_url = _resolve_thread_url(client, url)
        data = _fetch_thread_json(client, thread_url)

    # Reddit returns a list: [post_listing, comments_listing]
    post_data = data[0]["data"]["children"][0]["data"]
    title = post_data.get("title", "")
    selftext = post_data.get("selftext", "")
    subreddit = post_data.get("subreddit", "")

    parts = [f"Subreddit: r/{subreddit}", f"Title: {title}"]
    if selftext:
        parts.append(f"\nPost body:\n{selftext}")

    # Extract top-level comments
    comments = data[1]["data"]["children"]
    top_comments = []
    for c in comments:
        if c["kind"] != "t1":
            continue
        body = c["data"].get("body", "").strip()
        author = c["data"].get("author", "[deleted]")
        score = c["data"].get("score", 0)
        if body:
            top_comments.append(f"[u/{author}, {score} pts] {body}")

    if top_comments:
        parts.append(f"\nTop comments ({len(top_comments)}):")
        parts.extend(top_comments[:20])  # Cap at 20 comments

    return "\n".join(parts)


def _resolve_thread_url(client: httpx.Client, url: str) -> str:
    """Resolve share/short links to a canonical Reddit thread URL."""
    normalized_url = _normalize_reddit_url(url)
    if not _needs_resolution(normalized_url):
        return normalized_url

    resp = client.get(url)
    resp.raise_for_status()
    return _normalize_reddit_url(str(resp.url))


def _fetch_thread_json(client: httpx.Client, url: str) -> list[dict]:
    """Fetch the Reddit JSON listing for a thread."""
    json_url = _build_json_url(url)
    resp = client.get(json_url)
    resp.raise_for_status()

    if not _looks_like_json(resp):
        preview = _response_preview(resp)
        content_type = resp.headers.get("content-type", "unknown")
        message = f"Expected Reddit JSON from {resp.url}, got {content_type}"
        if preview:
            message += f": {preview}"
        raise RuntimeError(message)

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        preview = _response_preview(resp)
        message = f"Reddit returned invalid JSON from {resp.url}"
        if preview:
            message += f": {preview}"
        raise RuntimeError(message) from exc

    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError(f"Unexpected Reddit JSON structure from {resp.url}")

    return data


def _needs_resolution(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]

    return host == "redd.it" or (
        "reddit.com" in host and len(segments) >= 2 and segments[-2] == "s"
    )


def _normalize_reddit_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith(".json"):
        path = path[:-5]

    normalized = parsed._replace(path=path.rstrip("/"), query="", fragment="")
    return urlunparse(normalized)


def _build_json_url(url: str) -> str:
    parsed = urlparse(_normalize_reddit_url(url))
    return urlunparse(parsed._replace(path=f"{parsed.path}.json"))


def _looks_like_json(resp: httpx.Response) -> bool:
    content_type = resp.headers.get("content-type", "").lower()
    if "json" in content_type:
        return True

    stripped = resp.text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _response_preview(resp: httpx.Response) -> str:
    first_line = resp.text.strip().splitlines()
    if not first_line:
        return ""
    return first_line[0][:120]
