# glance

CLI (and optional tiny web app) to summarize YouTube videos, Reddit threads, and X posts — without exposing yourself to the algorithm.

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
- **Web** (remote): set `LLM_PROVIDER=web` and `GLANCE_WEB_URL=http://<host>:8765` to delegate the LLM call to a remote glance-web instance over the network (e.g. a GPU box on your tailnet). The remote machine's own `LLM_PROVIDER` decides whether it answers via Anthropic or Ollama — invisible to the caller. Glance posts pre-fetched content to `POST /llm`, so the remote doesn't re-fetch the source URL.

## Usage
```bash
uv run glance "https://x.com/xyz/status/..."
uv run glance --provider ollama "https://www.youtube.com/watch?v=..."
```

## Web mode (mobile-friendly)

There is also a tiny FastAPI wrapper so you can paste a URL from your phone and get a streamed summary. Useful when your server is on a Tailscale tailnet alongside your phone.

```bash
uv run glance-web              # binds to GLANCE_HOST:GLANCE_PORT (defaults 0.0.0.0:8765)
```

Then open `http://<server>:8765/` and **Add to Home Screen** for an app-like launcher. The page streams chunks via Server-Sent Events as the model generates.

Relevant `.env` knobs:

- `GLANCE_HOST` / `GLANCE_PORT` — bind address. Set `GLANCE_HOST` to a Tailscale IP to expose only on the tailnet.
- `GLANCE_OLLAMA_KEEP_ALIVE` — seconds (or `"5m"`-style duration) Ollama keeps the model in VRAM after each request. Defaults to `0` (unload immediately) so the GPU is free for other workloads.

### Run it as a systemd service

A unit file is provided at `deploy/glance-web.service`. Edit `User=`, `WorkingDirectory=`, and the `uv` path if your layout differs, then:

```bash
sudo cp deploy/glance-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now glance-web
systemctl status glance-web
```

Logs: `journalctl -u glance-web -f`.

## Structure
```
src/glance/
├── cli.py          # entry point, URL detection
├── youtube.py      # yt-dlp transcript extraction
├── reddit.py       # Reddit JSON thread fetching
├── twitter.py      # Twitter/X oEmbed fetching
├── summarize.py    # LLM summarization (Anthropic or Ollama), streaming
└── web.py          # FastAPI wrapper (glance-web entry point)
deploy/
└── glance-web.service  # example systemd unit
```
