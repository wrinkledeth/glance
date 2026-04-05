# glance

Summarize threads / videos without exposing yourself to toxic algos.

Supported sites:
- youtube
- reddit

## Why

You want the information, not the platform. Glance fetches content headlessly and pipes it through Claude for a summary. Cold Turkey stays locked forever. You never open a browser tab.

## How it works

1. Paste a URL into the CLI
2. Glance detects the source (YouTube or Reddit)
3. Fetches content headlessly — `yt-dlp` for transcripts, Reddit's JSON API for threads
4. Pipes it to Claude for a summary
5. Prints the summary to your terminal

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone and install
git clone <repo-url>
cd glance
uv sync

# Install yt-dlp (needed for YouTube)
uv tool install yt-dlp

# Set up your API key
cp .env.example .env
# Edit .env with your Anthropic API key
source .env
```

## Usage

```bash
# Summarize a YouTube video
uv run glance "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Summarize a Reddit thread
uv run glance "https://www.reddit.com/r/python/comments/abc123/some_thread/"
```

## Project structure

```
glance/
├── pyproject.toml            # Project config and dependencies
├── .env.example              # API key template
├── src/glance/
│   ├── cli.py                # Entry point, URL detection
│   ├── youtube.py            # yt-dlp transcript extraction
│   ├── reddit.py             # Reddit JSON thread fetching
│   └── summarize.py          # Claude API summarization
```

## Future ideas

- MCP server so you can call it from Claude directly
- More sources (HN, Twitter/X, articles)
- Configurable summary length/style
- Local LLM support


