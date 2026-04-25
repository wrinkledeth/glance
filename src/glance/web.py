import json
import os
import traceback
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from glance.cli import detect_source
from glance.summarize import ANTHROPIC_MODEL, _stream_anthropic, _stream_ollama, summarize_stream


app = FastAPI(title="glance")


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="glance">
<meta name="theme-color" content="#0b0b0d">
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
  h1 { font-size: 1.1rem; margin: 8px 0 12px; letter-spacing: 0.02em; opacity: 0.7; font-weight: 500; }
  form { display: flex; gap: 8px; }
  input[type=url] {
    flex: 1; min-width: 0;
    padding: 12px 14px; font-size: 16px;
    background: #161619; color: #e6e6e6;
    border: 1px solid #2a2a2f; border-radius: 10px;
    -webkit-appearance: none; appearance: none;
  }
  input[type=url]:focus { outline: none; border-color: #4a8cff; }
  button {
    padding: 12px 16px; font-size: 16px; font-weight: 600;
    background: #4a8cff; color: #fff;
    border: 0; border-radius: 10px;
    -webkit-appearance: none; appearance: none;
  }
  button:disabled { opacity: 0.5; }
  .out-head {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    min-height: 34px; margin: 12px 0 4px;
  }
  #status {
    flex: 1; min-width: 0;
    font-size: 13px; opacity: 0.6; min-height: 1.2em;
  }
  #out {
    white-space: pre-wrap; word-wrap: break-word;
    background: #111114; border: 1px solid #1f1f23; border-radius: 10px;
    padding: 14px;
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    min-height: 4em;
  }
  #copy {
    flex: 0 0 auto;
    width: 92px; padding: 6px 10px; font-size: 13px; text-align: center;
    background: #1c1c21; color: #e6e6e6;
    border: 1px solid #2a2a2f; border-radius: 8px;
    visibility: hidden; pointer-events: none;
  }
  #copy.show { visibility: visible; pointer-events: auto; }
  #copy.ok { background: #1f3a1f; border-color: #2f5a2f; }
</style>
</head>
<body>
<main>
  <h1>glance</h1>
  <form id="f">
    <input id="u" type="url" inputmode="url" autocapitalize="off" autocorrect="off"
           spellcheck="false" placeholder="paste a YouTube / Reddit / X / HN / article URL" required>
    <button id="go" type="submit">Go</button>
  </form>
  <div class="out-head">
    <div id="status"></div>
    <button id="copy" type="button">copy</button>
  </div>
  <div id="out"></div>
</main>
<script>
  const f = document.getElementById('f');
  const u = document.getElementById('u');
  const go = document.getElementById('go');
  const status = document.getElementById('status');
  const out = document.getElementById('out');
  const copy = document.getElementById('copy');
  let es = null;

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

  f.addEventListener('submit', (e) => {
    e.preventDefault();
    if (es) { es.close(); es = null; }
    out.textContent = '';
    copy.classList.remove('show', 'ok');
    copy.textContent = 'copy';
    status.textContent = 'fetching…';
    go.disabled = true;
    const url = u.value.trim();
    es = new EventSource('/summarize?url=' + encodeURIComponent(url));
    es.addEventListener('status', (ev) => { status.textContent = ev.data; });
    es.addEventListener('chunk', (ev) => {
      out.textContent += JSON.parse(ev.data);
      if (out.textContent) copy.classList.add('show');
      window.scrollTo(0, document.body.scrollHeight);
    });
    es.addEventListener('error', (ev) => {
      if (ev.data) status.textContent = 'error: ' + ev.data;
      es.close(); es = null; go.disabled = false;
    });
    es.addEventListener('done', () => {
      status.textContent = 'done';
      es.close(); es = null; go.disabled = false;
    });
  });

  copy.addEventListener('click', async () => {
    try {
      await copyText(out.textContent);
      copy.textContent = 'copied!';
      copy.classList.add('ok');
      setTimeout(() => {
        copy.textContent = 'copy';
        copy.classList.remove('ok');
      }, 1200);
    } catch {
      copy.textContent = 'copy failed';
      setTimeout(() => { copy.textContent = 'copy'; }, 1500);
    }
  });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


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


def _summarize_events(url: str, provider: str | None) -> Iterator[str]:
    source = detect_source(url)

    try:
        yield _sse("status", f"fetching {source}…")
        content = _fetch_content(source, url)
        yield _sse("status", "summarizing…")
        for chunk in summarize_stream(content, source, provider=provider):
            yield _sse("chunk", json.dumps(chunk))
        yield _sse("done", "")
    except Exception as exc:
        traceback.print_exc()
        yield _sse("error", str(exc) or exc.__class__.__name__)


@app.get("/summarize")
def summarize_endpoint(
    url: str = Query(...),
    provider: str | None = Query(None),
) -> StreamingResponse:
    return StreamingResponse(
        _summarize_events(url, provider),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class LLMRequest(BaseModel):
    content: str
    system: str | None = None
    source_type: str | None = None


def _resolve_provider_model() -> tuple[str, str]:
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        return provider, ANTHROPIC_MODEL
    if provider == "ollama":
        return provider, os.getenv("OLLAMA_MODEL", "qwen3.5:35B-A3B")
    return provider, "?"


def _llm_events(req: LLMRequest) -> Iterator[str]:
    try:
        provider, model = _resolve_provider_model()
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
    host = os.getenv("GLANCE_HOST", "0.0.0.0")
    port = int(os.getenv("GLANCE_PORT", "8765"))
    uvicorn.run("glance.web:app", host=host, port=port, log_level="info")
