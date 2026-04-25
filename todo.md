# glance — feature / QoL ideas

## Low-effort QoL
- **History / cache.** Save `(url, summary, timestamp)` to a SQLite file in `~/.cache/glance/`. Re-pasting a URL returns instantly; `glance --history` lists past summaries. Saves Anthropic tokens and is great on mobile when you re-open something.
- **Clipboard mode.** `glance` with no args reads from `$CLIPBOARD` (or `wl-paste`/`pbpaste`). One-keystroke flow.
- **Copy-to-clipboard button** in the web UI (mobile especially — the streamed text is hard to select).

## New sources
The architecture already separates by domain.
- **Generic article URLs** via `trafilatura` or `readability-lxml`. Probably the highest-utility addition — covers blogs, news, substack.
- **Hacker News threads** (Algolia API is trivial).
- **arXiv / PDF** via `pypdf` — paste a paper link, get the gist.
- **Podcasts / arbitrary audio** — `yt-dlp` is already in the stack; pipe to `whisper.cpp` or a hosted transcription endpoint.

## Output / integrations
- **Export to Obsidian / a markdown notes dir.** A `--save ~/notes/glance/` flag that writes a dated markdown file with the source URL + summary.
- IOS Share extension shortcut.

## Top picks
1. **Generic-article support** — biggest reach expansion.
