# AGENTS.md

Design philosophy for `glance`. Read this before proposing features so you don't re-derive assumptions that have already been thought through and rejected.

## What glance is

A capture tool. The user receives a link from a friend, or wants to research something on Reddit/YouTube/HN/etc. without enabling their URL blockers, and wants a summary. Paste URL, get summary. That's it.

It is not a feed reader, a knowledge base, a notes app, or a research assistant.

## Operating context

- **Primary backend is local GPU** (moodylotus on the tailnet, via the `web` or `ollama` provider). LLM calls are effectively free.
- **Anthropic is the fallback**, mostly used when the user is away from their tailnet.
- **Single user.** No multi-tenancy concerns. Auth is recommended (a bearer token would do) but not because of scale — because port-forwarding accidents happen.

Implication: **do not propose features whose justification is "saves tokens."** Cache-hit-on-re-paste, prompt compression, smaller-cheaper models, batch APIs — all irrelevant. Propose features that improve quality, ergonomics, or reach.

## Workflow assumptions

- **Capture is one-shot.** A URL is pasted once. Re-pasting the same URL is rare enough to ignore. Don't optimize for it.
- **Browse on the web, capture anywhere.** History viewing is a webapp-only concern (no `glance --history`). The CLI exists for the moment you're already in a terminal.
- **The cache is a write-only history log**, not a hot lookup. Every generation is fresh; every successful generation is persisted; retrieval happens through `/history` and `/s/{id}`.

## Things explicitly rejected

If a future suggestion looks like one of these, it has already been considered and rejected:

- Input autocomplete / recent-URL dropdown
- Tags, folders, collections
- Multiple export formats (the `--save` flag in `todo.md` covers Obsidian)
- A `--fresh` flag (re-generation is the only mode)
- A CLI `--history` browser
- Plugin systems / source registries
- Templating engines or JS frameworks for the web UI

## Architecture conventions

- **Per-source fetchers are flat.** `youtube.py`, `reddit.py`, `hn.py`, `twitter.py`, `article.py` each export a fetch function returning a string for the LLM. New sources slot in the same way — add a module, add a branch in `detect_source` and the `_fetch_content` dispatch.
- **The web UI lives inline in `web.py`.** HTML/CSS/JS are string constants. Don't pull in Jinja, React, htmx, etc. If a single page grows painful, extract just that page's HTML to a sibling file read at startup — keep the rest inline.
- **One SQLite file at `~/.cache/glance/glance.db`** (or `$GLANCE_DB`). Plain `sqlite3`, no ORM. Currently one table (`summaries`); add tables freely, but think twice before adding columns to existing ones.

## When in doubt

Ask whether the proposed feature serves the capture-once-then-browse flow. If it serves a workflow the user doesn't have ("subscribe to summaries," "share with team," "tag and organize"), drop it.
