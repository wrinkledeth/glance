import httpx


def fetch_thread(url: str) -> str:
    """Fetch a Reddit thread and return structured text for summarization."""
    # Normalize URL: strip trailing slash, append .json
    clean_url = url.rstrip("/")
    if not clean_url.endswith(".json"):
        clean_url += ".json"

    resp = httpx.get(
        clean_url,
        headers={"User-Agent": "glance-cli/0.1"},
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()

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
