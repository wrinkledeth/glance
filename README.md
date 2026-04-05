# glance

Summarize YouTube videos, Reddit threads, and X posts — without handing your attention to the algorithm.

## How it works

Paste a URL → glance fetches content headlessly → Claude summarizes it → printed to your terminal.

No browser tab. No autoplay. No "recommended for you." Just the info you asked for.

- **YouTube** — transcript via `yt-dlp`
- **Reddit** — thread via JSON API  
- **X / Twitter** — tweet via oEmbed API

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).
```bash
git clone <repo-url> && cd glance
uv sync
uv tool install yt-dlp        # needed for YouTube
cp .env.example .env          # add your Anthropic API key
```

## Usage
```bash
uv run glance "https://x.com/xyz/status/..."
```

## Structure
```
src/glance/
├── cli.py          # entry point, URL detection
├── youtube.py      # yt-dlp transcript extraction
├── reddit.py       # Reddit JSON thread fetching
├── twitter.py      # Twitter/X oEmbed fetching
└── summarize.py    # Claude API summarization
```
