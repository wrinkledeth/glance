import asyncio
import base64
import html
import json
import os
import secrets
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from glance.cli import detect_source
from glance import store
from glance.summarize import _stream_anthropic, _stream_ollama, resolve_model, summarize_stream


app = FastAPI(title="glance")

ICON_HEADERS = {"Cache-Control": "public, max-age=86400"}

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#0b0b0d"/>
<path d="M10 33c5.5-9 13-14 22-14s16.5 5 22 14c-5.5 8-13 12-22 12s-16.5-4-22-12Z" fill="none" stroke="#c9c9cf" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="32" cy="32" r="8" fill="#4a8cff"/>
<circle cx="32" cy="32" r="3.5" fill="#090d16"/>
<circle cx="29.5" cy="29" r="1.8" fill="#e6eeff"/>
</svg>
"""

APPLE_TOUCH_ICON_PNG = base64.b64decode(
    "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"
    "lNAAAAAElFTkSuQmCC"
)

WEB_MANIFEST = {
    "name": "glance",
    "short_name": "glance",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#0b0b0d",
    "theme_color": "#0b0b0d",
    "icons": [
        {
            "src": "/favicon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any",
        },
        {
            "src": "/apple-touch-icon.png",
            "sizes": "180x180",
            "type": "image/png",
            "purpose": "any maskable",
        },
    ],
}


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="glance">
<meta name="theme-color" content="#0b0b0d">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<title>glance</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body {
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #0b0b0d; color: #e6e6e6;
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
  }
  main { max-width: 720px; margin: 0 auto; padding: 16px; }
  .topbar { display: flex; align-items: center; justify-content: space-between; margin: 8px 0 14px; }
  .topbar h1 {
    font-size: 1.1rem; margin: 0; letter-spacing: 0.02em;
    opacity: 0.75; font-weight: 500; line-height: 1;
  }
  .topbar h1 a {
    display: inline-flex; align-items: center; gap: 0.5em;
    color: inherit; text-decoration: none;
  }
  .topbar h1 svg { width: 1.15em; height: 1.15em; display: block; transform: translateY(0.06em); }
  .topbar nav { font-size: 0.9rem; opacity: 0.65; display: flex; gap: 14px; }
  .topbar nav a { color: inherit; text-decoration: none; }
  .topbar nav a:hover { color: #4a8cff; }
  .topbar nav a.active { color: #e6e6e6; opacity: 1; }
  form { display: block; }
  .url-wrap { position: relative; display: flex; }
  input[type=url] {
    flex: 1; min-width: 0;
    padding: 13px 86px 13px 14px; font-size: 16px;
    background: #161619; color: #e6e6e6;
    border: 1px solid #2a2a2f; border-radius: 12px;
    -webkit-appearance: none; appearance: none;
    transition: border-color 120ms ease;
  }
  input[type=url]:focus { outline: none; border-color: #4a8cff; }
  .url-actions {
    position: absolute; top: 50%; right: 5px; transform: translateY(-50%);
    display: flex; align-items: center; gap: 2px;
  }
  .icon-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; padding: 0;
    background: transparent; color: rgba(230, 230, 230, 0.55);
    border: 0; border-radius: 7px; cursor: pointer;
    -webkit-appearance: none; appearance: none;
    visibility: hidden; pointer-events: none;
    transition: background-color 120ms ease, color 120ms ease, transform 80ms ease;
  }
  .icon-btn svg { width: 14px; height: 14px; stroke-width: 1.8; }
  .icon-btn.show { visibility: visible; pointer-events: auto; }
  .icon-btn:hover { background: rgba(255, 255, 255, 0.04); color: rgba(230, 230, 230, 0.86); }
  .icon-btn:active { background: rgba(255, 255, 255, 0.03); transform: translateY(1px); }
  .icon-btn:focus-visible { outline: 2px solid #4a8cff; outline-offset: 2px; }
  .icon-btn.ok { color: #9ecf9e; }
  .url-actions .divider {
    width: 1px; height: 18px; background: rgba(255,255,255,0.08); margin: 0 2px;
    opacity: 0; transition: opacity 120ms ease;
  }
  .url-actions .divider.show { opacity: 1; }
  #go {
    width: 34px; height: 34px; border-radius: 9px;
    background: #2a2a2f; color: rgba(230, 230, 230, 0.45);
    visibility: visible; pointer-events: auto;
    transition: background-color 140ms ease, color 140ms ease, transform 80ms ease;
  }
  #go svg { width: 16px; height: 16px; stroke-width: 2; }
  #go.ready { background: #4a8cff; color: #fff; }
  #go.ready:hover { background: #3a7af0; }
  #go:disabled { cursor: not-allowed; }
  #go.busy { background: #2a2a2f; color: rgba(230, 230, 230, 0.35); }
  .out-head {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    min-height: 34px; margin: 12px 0 4px;
  }
  #status {
    flex: 1; min-width: 0;
    font-size: 13px; opacity: 0.6; min-height: 1.2em;
    transition: color 200ms ease;
  }
  #status.error { color: #e88b8b; opacity: 0.85; }
  #out {
    white-space: pre-wrap; word-wrap: break-word;
    background: #111114; border: 1px solid #1f1f23; border-radius: 10px;
    padding: 14px;
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    min-height: 4em;
  }
  #copy {
    float: right; margin: -2px 0 4px 8px;
    visibility: visible; pointer-events: auto;
    display: none;
  }
  #copy.show { display: inline-flex; }
  #copy .check { display: none; }
  #copy.ok .clip { display: none; }
  #copy.ok .check { display: inline; }
</style>
</head>
<body>
<main>
__TOPBAR__
  <form id="f">
    <div class="url-wrap">
      <input id="u" type="url" inputmode="url" autocapitalize="off" autocorrect="off"
             spellcheck="false" placeholder="paste a YouTube / Reddit / X / HN / article URL" required>
      <div class="url-actions">
        <button id="ucopy" class="icon-btn" type="button" aria-label="Copy URL" title="Copy URL">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true" focusable="false">
            <rect x="8" y="8" width="11" height="11" rx="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1"></path>
          </svg>
        </button>
        <button id="uclear" class="icon-btn" type="button" aria-label="Clear URL" title="Clear URL">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" aria-hidden="true" focusable="false">
            <path d="M6 6 L18 18 M18 6 L6 18"></path>
          </svg>
        </button>
        <span id="divider" class="divider"></span>
        <button id="go" class="icon-btn" type="submit" aria-label="Summarize" title="Summarize">
          <svg class="arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
            <path d="M5 12h14"></path>
            <path d="M13 6l6 6-6 6"></path>
          </svg>
        </button>
      </div>
    </div>
  </form>
  <div class="out-head">
    <div id="status"></div>
  </div>
  <div id="out"><button id="copy" class="icon-btn" type="button" aria-label="Copy summary" title="Copy summary"><svg class="clip" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true" focusable="false"><rect x="8" y="8" width="11" height="11" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1"></path></svg><svg class="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12.5 L10 17.5 L19 7.5"></path></svg></button><span id="out-text"></span></div>
</main>
<script>
  const f = document.getElementById('f');
  const u = document.getElementById('u');
  const go = document.getElementById('go');
  const status = document.getElementById('status');
  const out = document.getElementById('out');
  const outText = document.getElementById('out-text');
  const copy = document.getElementById('copy');
  const ucopy = document.getElementById('ucopy');
  const uclear = document.getElementById('uclear');
  const divider = document.getElementById('divider');
  let pollingId = null;
  const JOB_KEY = 'glance.job';

  function setStatus(text, kind) {
    status.textContent = text;
    status.classList.toggle('error', kind === 'error');
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  function resetOutput() {
    outText.textContent = '';
    copy.classList.remove('show', 'ok');
  }

  async function pollJob(jobId) {
    if (pollingId === jobId) return;
    pollingId = jobId;
    let cursor = 0;
    resetOutput();
    setStatus('resuming…');
    setBusy(true);
    try {
      while (pollingId === jobId) {
        let resp;
        try {
          resp = await fetch('/summarize/' + encodeURIComponent(jobId) + '?cursor=' + cursor);
        } catch (_) {
          await sleep(800);
          continue;
        }
        if (resp.status === 404) {
          localStorage.removeItem(JOB_KEY);
          setStatus('job expired', 'error');
          break;
        }
        if (!resp.ok) {
          await sleep(800);
          continue;
        }
        const data = await resp.json();
        for (const ev of data.events) {
          if (ev.kind === 'status') {
            setStatus(ev.data);
          } else if (ev.kind === 'chunk') {
            outText.textContent += ev.data;
            if (outText.textContent) copy.classList.add('show');
            window.scrollTo(0, document.body.scrollHeight);
          } else if (ev.kind === 'done') {
            setStatus('done');
            if (ev.data) {
              try { history.replaceState(null, '', '/s/' + ev.data); } catch {}
            }
          } else if (ev.kind === 'error') {
            setStatus('error: ' + ev.data, 'error');
          }
        }
        cursor = data.next_cursor;
        if (data.status !== 'running') {
          localStorage.removeItem(JOB_KEY);
          break;
        }
        await sleep(400);
      }
    } finally {
      if (pollingId === jobId) pollingId = null;
      setBusy(false);
    }
  }

  function refreshUrlActions() {
    const has = u.value.length > 0;
    ucopy.classList.toggle('show', has);
    uclear.classList.toggle('show', has);
    divider.classList.toggle('show', has);
    if (!go.classList.contains('busy')) {
      go.classList.toggle('ready', has);
    }
  }
  u.addEventListener('input', refreshUrlActions);
  refreshUrlActions();

  ucopy.addEventListener('click', async () => {
    if (!u.value) return;
    try {
      await copyText(u.value);
      ucopy.classList.add('ok');
      setTimeout(() => ucopy.classList.remove('ok'), 1000);
    } catch {}
  });
  uclear.addEventListener('click', () => {
    u.value = '';
    refreshUrlActions();
    u.focus();
  });

  async function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      if (!document.execCommand('copy')) {
        throw new Error('copy failed');
      }
    } finally {
      document.body.removeChild(ta);
    }
  }

  f.addEventListener('submit', async (e) => {
    e.preventDefault();
    pollingId = null;
    resetOutput();
    setStatus('starting…');
    setBusy(true);
    const url = u.value.trim();
    try {
      const resp = await fetch('/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      if (!resp.ok) {
        let msg = 'failed to start (' + resp.status + ')';
        try { const j = await resp.json(); if (j && j.detail) msg = j.detail; } catch (_) {}
        throw new Error(msg);
      }
      const { job_id } = await resp.json();
      localStorage.setItem(JOB_KEY, job_id);
      pollJob(job_id);
    } catch (err) {
      setStatus('error: ' + err.message, 'error');
      setBusy(false);
    }
  });

  function setBusy(busy) {
    go.disabled = busy;
    go.classList.toggle('busy', busy);
    if (busy) {
      go.classList.remove('ready');
    } else {
      refreshUrlActions();
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    const jid = localStorage.getItem(JOB_KEY);
    if (jid && pollingId !== jid) pollJob(jid);
  });

  (() => {
    const jid = localStorage.getItem(JOB_KEY);
    if (jid) pollJob(jid);
  })();

  copy.addEventListener('click', async () => {
    try {
      await copyText(outText.textContent);
      copy.classList.add('ok');
      setTimeout(() => copy.classList.remove('ok'), 1200);
    } catch {}
  });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.replace("__TOPBAR__", _topbar("new")))


@app.get("/favicon.svg")
def favicon() -> Response:
    return Response(FAVICON_SVG, media_type="image/svg+xml", headers=ICON_HEADERS)


@app.get("/apple-touch-icon.png")
def apple_touch_icon() -> Response:
    return Response(APPLE_TOUCH_ICON_PNG, media_type="image/png", headers=ICON_HEADERS)


@app.get("/site.webmanifest")
def site_webmanifest() -> Response:
    return Response(
        json.dumps(WEB_MANIFEST),
        media_type="application/manifest+json",
        headers=ICON_HEADERS,
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


def _fetch_content(source: str, url: str) -> str:
    if source == "youtube":
        from glance.youtube import extract_transcript
        return extract_transcript(url)
    if source == "reddit":
        from glance.reddit import fetch_thread
        return fetch_thread(url)
    if source == "twitter":
        from glance.twitter import fetch_tweet
        return fetch_tweet(url)
    if source == "hn":
        from glance.hn import fetch_hn
        return fetch_hn(url)
    if source == "article":
        from glance.article import fetch_article
        return fetch_article(url)
    raise ValueError(f"unsupported source: {source}")


@dataclass
class Job:
    id: str
    events: list[dict] = field(default_factory=list)
    status: str = "running"
    created_at: float = field(default_factory=time.time)


_JOBS: dict[str, Job] = {}
_JOB_TTL_SEC = 600


def _sweep_jobs() -> None:
    now = time.time()
    expired = [
        jid for jid, j in _JOBS.items()
        if j.status != "running" and now - j.created_at > _JOB_TTL_SEC
    ]
    for jid in expired:
        _JOBS.pop(jid, None)


def _run_job_sync(job: Job, url: str, provider: str | None) -> None:
    try:
        source = detect_source(url)
        _, model = resolve_model(provider)

        job.events.append({"kind": "status", "data": f"fetching {source}…"})
        content = _fetch_content(source, url)
        job.events.append({"kind": "status", "data": "summarizing…"})
        parts: list[str] = []
        for chunk in summarize_stream(content, source, provider=provider):
            parts.append(chunk)
            job.events.append({"kind": "chunk", "data": chunk})
        summary = "".join(parts)
        sid = store.put(url, source, model, summary) if summary.strip() else ""
        job.events.append({"kind": "done", "data": sid})
        job.status = "done"
    except Exception as exc:
        traceback.print_exc()
        job.events.append({"kind": "error", "data": str(exc) or exc.__class__.__name__})
        job.status = "error"


class SummarizeRequest(BaseModel):
    url: str
    provider: str | None = None


@app.post("/summarize")
async def summarize_start(req: SummarizeRequest) -> dict:
    _sweep_jobs()
    job_id = secrets.token_urlsafe(12)
    job = Job(id=job_id)
    _JOBS[job_id] = job
    asyncio.create_task(asyncio.to_thread(_run_job_sync, job, req.url, req.provider))
    return {"job_id": job_id}


@app.get("/summarize/{job_id}")
def summarize_poll(job_id: str, cursor: int = 0) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return {
        "events": job.events[cursor:],
        "next_cursor": len(job.events),
        "status": job.status,
    }


SHARED_HEAD = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0b0d">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #0b0b0d; color: #e6e6e6;
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
  }
  main { max-width: 720px; margin: 0 auto; padding: 16px; }
  a { color: #4a8cff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .topbar { display: flex; align-items: center; justify-content: space-between; margin: 8px 0 14px; }
  .topbar h1 {
    font-size: 1.1rem; margin: 0; letter-spacing: 0.02em;
    opacity: 0.75; font-weight: 500; line-height: 1;
  }
  .topbar h1 a {
    display: inline-flex; align-items: center; gap: 0.5em;
    color: inherit; text-decoration: none;
  }
  .topbar h1 svg { width: 1.15em; height: 1.15em; display: block; transform: translateY(0.06em); }
  .topbar nav { font-size: 0.9rem; opacity: 0.65; display: flex; gap: 14px; }
  .topbar nav a { color: inherit; text-decoration: none; }
  .topbar nav a:hover { color: #4a8cff; }
  .topbar nav a.active { color: #e6e6e6; opacity: 1; }
  .summary {
    white-space: pre-wrap; word-wrap: break-word;
    background: #111114; border: 1px solid #1f1f23; border-radius: 10px;
    padding: 14px;
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  }
  .meta { font-size: 13px; opacity: 0.6; margin: 0 0 12px; }
  .meta .source { text-transform: lowercase; }
  ul.history { list-style: none; padding: 0; margin: 0; }
  ul.history li {
    padding: 12px 0; border-bottom: 1px solid #1f1f23;
  }
  ul.history li:last-child { border-bottom: 0; }
  ul.history .row1 {
    display: flex; gap: 8px; align-items: baseline; font-size: 13px; opacity: 0.6;
  }
  ul.history .row1 .source { text-transform: lowercase; }
  ul.history .title { display: block; margin: 2px 0 4px; font-size: 15px; }
  ul.history .preview { font-size: 14px; opacity: 0.75; }
  input.search {
    width: 100%; padding: 10px 12px; font-size: 16px;
    background: #161619; color: #e6e6e6;
    border: 1px solid #2a2a2f; border-radius: 10px;
    -webkit-appearance: none; appearance: none; margin-bottom: 12px;
  }
  input.search:focus { outline: none; border-color: #4a8cff; }
</style>
"""


LOGO_SVG = (
    '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="5" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<path d="M10 33c5.5-9 13-14 22-14s16.5 5 22 14c-5.5 8-13 12-22 12s-16.5-4-22-12Z"/>'
    '<circle cx="32" cy="32" r="5" fill="currentColor" stroke="none"/>'
    "</svg>"
)


def _topbar(active: str = "") -> str:
    def link(href: str, label: str) -> str:
        cls = ' class="active"' if active == label else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return (
        '<div class="topbar">'
        f'<h1><a href="/">{LOGO_SVG}<span>glance</span></a></h1>'
        f'<nav>{link("/", "new")}{link("/history", "history")}</nav>'
        "</div>"
    )


def _fmt_time(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def _first_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s
    return ""


@app.get("/s/{summary_id}", response_class=HTMLResponse)
def summary_page(summary_id: str) -> HTMLResponse:
    s = store.get_by_id(summary_id)
    if s is None:
        raise HTTPException(404, "summary not found")
    body = (
        "<!doctype html><html lang=\"en\"><head>"
        + SHARED_HEAD
        + f"<title>glance — {html.escape(s.url)}</title>"
        + "</head><body><main>"
        + _topbar()
        + '<p class="meta">'
        + f'<span class="source">{html.escape(s.source)}</span> · '
        + f'{_fmt_time(s.created_at)} · '
        + f'<a href="{html.escape(s.url)}" rel="noopener noreferrer" target="_blank">source</a>'
        + "</p>"
        + f'<div class="summary">{html.escape(s.summary)}</div>'
        + "</main></body></html>"
    )
    return HTMLResponse(body)


HISTORY_HTML = """<!doctype html><html lang="en"><head>
""" + SHARED_HEAD + """<title>glance — history</title>
</head><body><main>
__TOPBAR__
<input id="q" class="search" type="search" placeholder="search url or summary text" autocomplete="off">
<ul id="list" class="history"></ul>
<script>
  const q = document.getElementById('q');
  const list = document.getElementById('list');
  const params = new URLSearchParams(location.search);
  if (params.get('q')) q.value = params.get('q');

  function fmtTime(ts) {
    const d = new Date(ts * 1000);
    const pad = (n) => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate())
      + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  let token = 0;
  async function load() {
    const my = ++token;
    const url = '/api/history' + (q.value ? '?q=' + encodeURIComponent(q.value) : '');
    const resp = await fetch(url);
    if (!resp.ok || my !== token) return;
    const data = await resp.json();
    if (my !== token) return;
    list.innerHTML = data.items.map(it => (
      '<li>'
      + '<div class="row1"><span class="source">' + escapeHtml(it.source) + '</span>'
      + ' · <span>' + fmtTime(it.created_at) + '</span></div>'
      + '<a class="title" href="/s/' + encodeURIComponent(it.id) + '">' + escapeHtml(it.url) + '</a>'
      + '<div class="preview">' + escapeHtml(it.preview) + '</div>'
      + '</li>'
    )).join('') || '<li style="opacity:0.5">no summaries yet</li>';
  }

  let timer = null;
  q.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(load, 150);
  });
  load();
</script>
</main></body></html>
"""


@app.get("/history", response_class=HTMLResponse)
def history_page() -> HTMLResponse:
    return HTMLResponse(HISTORY_HTML.replace("__TOPBAR__", _topbar("history")))


@app.get("/api/history")
def history_api(q: str | None = None, limit: int = Query(50, ge=1, le=200)) -> dict:
    items = store.list_recent(limit=limit, query=q)
    return {
        "items": [
            {
                "id": s.id,
                "url": s.url,
                "source": s.source,
                "created_at": s.created_at,
                "preview": _first_line(s.summary)[:200],
            }
            for s in items
        ]
    }


class LLMRequest(BaseModel):
    content: str
    system: str | None = None
    source_type: str | None = None


def _llm_events(req: LLMRequest) -> Iterator[str]:
    try:
        provider, model = resolve_model()
        yield json.dumps({"meta": {"provider": provider, "model": model}}) + "\n"

        if req.system:
            if provider == "anthropic":
                stream = _stream_anthropic(req.content, req.system)
            elif provider == "ollama":
                stream = _stream_ollama(req.content, req.system)
            else:
                raise RuntimeError(f"unsupported remote LLM_PROVIDER: {provider!r}")
        else:
            stream = summarize_stream(req.content, req.source_type)
        for chunk in stream:
            yield json.dumps({"chunk": chunk}) + "\n"
        yield json.dumps({"done": True}) + "\n"
    except Exception as exc:
        traceback.print_exc()
        yield json.dumps({"error": str(exc) or exc.__class__.__name__}) + "\n"


@app.post("/llm")
def llm_endpoint(req: LLMRequest) -> StreamingResponse:
    if not req.system and not req.source_type:
        raise HTTPException(400, "must provide 'system' or 'source_type'")
    return StreamingResponse(
        _llm_events(req),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def run() -> None:
    import uvicorn
    host = os.getenv("GLANCE_HOST", "127.0.0.1")
    port = int(os.getenv("GLANCE_PORT", "8765"))
    uvicorn.run("glance.web:app", host=host, port=port, log_level="info")
