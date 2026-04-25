import httpx
import trafilatura


USER_AGENT = "glance-cli/0.1"


def fetch_article(url: str) -> str:
    """Fetch a generic web article and return structured text for summarization."""
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    body = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if not body or not body.strip():
        raise RuntimeError(f"Could not extract article content from {url}")

    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata else None) or ""
    author = (metadata.author if metadata else None) or ""

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if author:
        parts.append(f"Author: {author}")
    parts.append(f"URL: {url}")
    parts.append("")
    parts.append(body.strip())
    return "\n".join(parts)
