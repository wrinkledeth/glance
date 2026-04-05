import argparse
import shutil
import sys
import textwrap
from urllib.parse import urlparse

from glance.summarize import summarize


def detect_source(url: str) -> str:
    """Detect whether a URL is YouTube, Reddit, or unknown."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if any(h in host for h in ("youtube.com", "youtu.be")):
        return "youtube"
    elif "reddit.com" in host or "redd.it" in host:
        return "reddit"
    else:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(
        prog="glance",
        description="Get LLM summaries of YouTube videos and Reddit threads",
    )
    parser.add_argument("url", help="YouTube or Reddit URL to summarize")
    args = parser.parse_args()

    source = detect_source(args.url)

    if source == "unknown":
        print(f"Error: unsupported URL: {args.url}", file=sys.stderr)
        print("Supported: YouTube, Reddit", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching {source} content...", file=sys.stderr)

    if source == "youtube":
        from glance.youtube import extract_transcript
        content = extract_transcript(args.url)
    elif source == "reddit":
        from glance.reddit import fetch_thread
        content = fetch_thread(args.url)

    print("Summarizing...", file=sys.stderr)
    result = summarize(content, source)
    width = shutil.get_terminal_size().columns
    for line in result.splitlines():
        if line.strip():
            indent = len(line) - len(line.lstrip())
            subsequent = indent + 2
            print(textwrap.fill(line, width=width, initial_indent="",
                                subsequent_indent=" " * subsequent))
        else:
            print()
