import httpx


def fetch_tweet(url: str) -> str:
    """Fetch a tweet/thread and return structured text for summarization."""
    # Use Twitter's public syndication API (no auth required)
    resp = httpx.get(
        "https://publish.twitter.com/oembed",
        params={"url": url, "omit_script": "true"},
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()

    author = data.get("author_name", "Unknown")
    html = data.get("html", "")

    # Strip HTML tags to get plain text
    import re
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"\n{2,}", "\n", text).strip()

    parts = [f"Author: {author}", f"\nTweet:\n{text}"]
    return "\n".join(parts)
