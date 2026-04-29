import argparse
import shutil
import sys
import textwrap
from urllib.parse import urlparse

from glance import store
from glance.summarize import resolve_model, summarize


def detect_source(url: str) -> str:
    """Detect the source type from a URL. Falls back to generic article."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if any(h in host for h in ("youtube.com", "youtu.be")):
        return "youtube"
    elif "reddit.com" in host or "redd.it" in host:
        return "reddit"
    elif host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"
    elif host == "tiktok.com" or host.endswith(".tiktok.com"):
        return "tiktok"
    elif any(h in host for h in ("twitter.com", "x.com")):
        return "twitter"
    elif "news.ycombinator.com" in host:
        return "hn"
    else:
        return "article"


def main():
    parser = argparse.ArgumentParser(
        prog="glance",
        description="Get LLM summaries of yt, ig, TikTok, reddit, x, hn, and article URLs",
    )
    parser.add_argument("url", help="URL to summarize (yt, ig, TikTok, reddit, x, hn, or any article)")
    parser.add_argument(
        "--provider",
        choices=["anthropic", "ollama", "web"],
        default=None,
        help="LLM provider to use (overrides LLM_PROVIDER env var)",
    )
    args = parser.parse_args()

    source = detect_source(args.url)

    try:
        _, model = resolve_model(args.provider)

        print(f"Fetching {source} content...", file=sys.stderr)
        if source == "youtube":
            from glance.youtube import extract_transcript
            content = extract_transcript(args.url)
        elif source == "reddit":
            from glance.reddit import fetch_thread
            content = fetch_thread(args.url)
        elif source == "instagram":
            from glance.instagram import fetch_instagram
            content = fetch_instagram(args.url)
        elif source == "tiktok":
            from glance.tiktok import fetch_tiktok
            content = fetch_tiktok(args.url)
        elif source == "twitter":
            from glance.twitter import fetch_tweet
            content = fetch_tweet(args.url)
        elif source == "hn":
            from glance.hn import fetch_hn
            content = fetch_hn(args.url)
        elif source == "article":
            from glance.article import fetch_article
            content = fetch_article(args.url)

        result = summarize(content, source, provider=args.provider)
        if result.strip():
            store.put(args.url, source, model, result)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    width = shutil.get_terminal_size().columns
    for line in result.splitlines():
        if line.strip():
            indent = len(line) - len(line.lstrip())
            subsequent = indent + 2
            print(textwrap.fill(line, width=width, initial_indent="",
                                subsequent_indent=" " * subsequent))
        else:
            print()
