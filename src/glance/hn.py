import html as html_mod
import re
from urllib.parse import parse_qs, urlparse

import httpx

from glance.article import fetch_article


USER_AGENT = "glance-cli/0.1"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"
MAX_COMMENTS = 20

_TAG_RE = re.compile(r"<[^>]+>")


def fetch_hn(url: str) -> str:
    """Fetch a Hacker News item (post + comments) and, if linked, the article."""
    item_id = _parse_item_id(url)

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        resp = client.get(ALGOLIA_ITEM_URL.format(id=item_id))
        resp.raise_for_status()
        item = resp.json()

    title = item.get("title") or ""
    author = item.get("author") or "[deleted]"
    points = item.get("points")
    external_url = item.get("url") or ""
    post_text = _strip_html(item.get("text") or "")

    parts = [
        f"Title: {title}",
        f"HN post by: {author}" + (f" ({points} pts)" if points is not None else ""),
        f"HN URL: https://news.ycombinator.com/item?id={item_id}",
        "",
        "=== Article ===",
    ]

    if external_url:
        try:
            parts.append(fetch_article(external_url))
        except Exception as exc:
            parts.append(f"(article fetch failed: {exc})")
    elif post_text:
        parts.append(f"(no external link — Ask/Show HN post body)\n\n{post_text}")
    else:
        parts.append("(no external link)")

    parts.append("")
    parts.append("=== Discussion ===")

    comments = _flatten_comments(item.get("children") or [])
    if not comments:
        parts.append("(no comments)")
    else:
        for c in comments[:MAX_COMMENTS]:
            indent = "  " * c["depth"]
            parts.append(f"{indent}[u/{c['author']}] {c['text']}")

    return "\n".join(parts)


def _parse_item_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.rstrip("/") != "/item":
        raise RuntimeError(
            f"Not an HN item URL (expected /item?id=...): {url}"
        )
    qs = parse_qs(parsed.query)
    ids = qs.get("id")
    if not ids or not ids[0].isdigit():
        raise RuntimeError(f"HN URL missing numeric id: {url}")
    return ids[0]


def _flatten_comments(children: list[dict], depth: int = 0) -> list[dict]:
    """Walk the comment tree in HN's display order, returning flat list."""
    out = []
    for c in children:
        if c.get("type") != "comment":
            continue
        text = _strip_html(c.get("text") or "")
        if not text:
            # Skip dead/deleted comments but still walk into their children
            out.extend(_flatten_comments(c.get("children") or [], depth + 1))
            continue
        out.append({
            "author": c.get("author") or "[deleted]",
            "text": text,
            "depth": depth,
        })
        out.extend(_flatten_comments(c.get("children") or [], depth + 1))
    return out


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = _TAG_RE.sub(" ", s)
    s = html_mod.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
