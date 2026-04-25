# glance

CLI tool to summarize YouTube videos, Reddit threads, and X posts — without exposing yourself to the algorithm.

No browser tab. No autoplay. No "For You." Just the content you asked for :)

## How it works

Paste a URL → glance fetches content headlessly → an LLM summarizes and prints to the terminal.

- **YouTube** — transcript via `yt-dlp`
- **Reddit** — thread via JSON API  
- **X / Twitter** — tweet via oEmbed API
- **LLM** — Anthropic Claude (cloud) or Ollama (local)

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).
```bash
git clone <repo-url> && cd glance
uv sync
uv tool install yt-dlp        # needed for YouTube — do NOT use apt's yt-dlp, it goes stale and YouTube blocks it
cp .env.example .env          # configure provider (see below)
```

### LLM provider

Configure in `.env` or override per-call with `--provider {anthropic,ollama}`.

- **Anthropic** (default): set `ANTHROPIC_API_KEY` and `LLM_PROVIDER=anthropic`.
- **Ollama** (local): set `LLM_PROVIDER=ollama`, make sure `ollama serve` is running, and pull a model (e.g. `ollama pull qwen3.5:35B-A3B`). Tune `OLLAMA_HOST` and `OLLAMA_MODEL` as needed. Tokens stream live to stderr while the local model runs.

## Usage
```bash
uv run glance "https://x.com/xyz/status/..."
uv run glance --provider ollama "https://www.youtube.com/watch?v=..."
```

## Structure
```
src/glance/
├── cli.py          # entry point, URL detection
├── youtube.py      # yt-dlp transcript extraction
├── reddit.py       # Reddit JSON thread fetching
├── twitter.py      # Twitter/X oEmbed fetching
└── summarize.py    # LLM summarization (Anthropic or Ollama)
```
