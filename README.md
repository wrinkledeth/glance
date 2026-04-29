# glance

CLI (and optional tiny web app) to summarize yt videos, ig/TikTok clips, reddit threads, x posts, hn submissions, and articles — without exposing yourself to the algorithm.

No browser tab. No autoplay. No "For You." Just the content you asked for :)

## How it works

Paste a URL → glance fetches content headlessly → an LLM summarizes and prints to the terminal.

- **YouTube** — transcript via `yt-dlp`
- **Instagram** — clip metadata/transcript and top comments via `yt-dlp`
- **TikTok** — clip metadata/transcript and top comments via `yt-dlp`
- **Reddit** — thread via JSON API
- **X / Twitter** — tweet via oEmbed API
- **Hacker News** — post + discussion via Algolia API (also fetches the linked article)
- **Articles** — generic web pages via `trafilatura` (used as the fallback for any unrecognized URL)
- **LLM** — Anthropic Claude (cloud) or Ollama (local)

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).
```bash
git clone <repo-url> && cd glance
uv sync
uv tool install yt-dlp        # needed for yt/ig/TikTok — do NOT use apt's yt-dlp, it goes stale and sites block it
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
uv run glance "https://www.instagram.com/reel/..."
uv run glance "https://www.tiktok.com/@user/video/..."
uv run glance "https://news.ycombinator.com/item?id=..."   # article + discussion
uv run glance "https://some.blog/post"                      # generic article fallback
```

## Web mode (mobile-friendly)

There is also a tiny FastAPI wrapper so you can paste a URL from your phone and get a streamed summary. Useful when your server is on a Tailscale tailnet alongside your phone.

```bash
uv run glance-web              # binds to GLANCE_HOST:GLANCE_PORT (defaults 127.0.0.1:8765)
```

By default glance-web binds to localhost. To expose it on your tailnet over TLS, front it with [`tailscale serve`](https://tailscale.com/kb/1242/tailscale-serve) (no firewall holes, no `0.0.0.0`):

```bash
tailscale serve --bg --https=8443 http://127.0.0.1:8765
```

Then open `https://<machine>.<tailnet>.ts.net:8443/` and **Add to Home Screen** for an app-like launcher. Tailscale's three TLS ports are `443`, `8443`, and `10000` — pick whichever isn't already taken by another service.

Generation runs as a background job on the server, decoupled from the HTTP request. The page polls for new chunks every ~400ms and stores the active job id in `localStorage`, so locking your phone, switching apps, or reloading the tab mid-generation will pick the summary back up where it left off (jobs are retained for 10 minutes after completion).

Every successful summary is persisted to a SQLite history. Re-pasting the exact same URL still generates a fresh summary, then updates the existing history entry instead of adding a duplicate. After generation the URL becomes `/s/<id>` so you can bookmark or share a single summary, and `/history` gives a searchable list of everything you've glanced at. CLI runs write to the same store.

Relevant `.env` knobs:

- `GLANCE_HOST` / `GLANCE_PORT` — bind address. Defaults to `127.0.0.1:8765`; front with `tailscale serve` for tailnet exposure.
- `GLANCE_OLLAMA_KEEP_ALIVE` — seconds (or `"5m"`-style duration) Ollama keeps the model in VRAM after each request. Defaults to `0` (unload immediately) so the GPU is free for other workloads.
- `GLANCE_DB` — path to the SQLite history file. Defaults to `~/.cache/glance/glance.db`.

### Run it as a systemd service

A unit file is provided at `deploy/glance-web.service`. Edit `User=`, `WorkingDirectory=`, and the `uv` path if your layout differs, then:

```bash
sudo cp deploy/glance-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now glance-web
systemctl status glance-web
```

If yt/ig/TikTok summaries fail under systemd with `No such file or directory: 'yt-dlp'`, the service is missing the user tool directory on `PATH`. `uv tool install yt-dlp` installs to `~/.local/bin`, but systemd does not always include that directory. Add an override:

```bash
sudo mkdir -p /etc/systemd/system/glance-web.service.d
sudo tee /etc/systemd/system/glance-web.service.d/10-path.conf >/dev/null <<'EOF'
[Service]
Environment=PATH=/home/zen/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF
sudo systemctl daemon-reload
sudo systemctl restart glance-web
```

Logs: `journalctl -u glance-web -f`.

## Structure
```
src/glance/
├── cli.py          # entry point, URL detection
├── youtube.py      # yt-dlp transcript extraction
├── instagram.py    # yt-dlp clip metadata/transcript/comments extraction
├── tiktok.py       # yt-dlp clip metadata/transcript/comments extraction
├── reddit.py       # Reddit JSON thread fetching
├── twitter.py      # Twitter/X oEmbed fetching
├── hn.py           # Hacker News (Algolia API) + linked-article fetch
├── article.py      # generic article extraction (trafilatura)
├── summarize.py    # LLM summarization (Anthropic or Ollama), streaming
├── store.py        # SQLite history (fresh summaries, one row per exact URL)
└── web.py          # FastAPI wrapper (glance-web entry point)
deploy/
└── glance-web.service  # example systemd unit
```
