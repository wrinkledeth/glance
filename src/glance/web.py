import base64
import json
import os
import traceback
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from glance.cli import detect_source
from glance.summarize import ANTHROPIC_MODEL, _stream_anthropic, _stream_ollama, summarize_stream


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
    "iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAYAAAA9zQYyAAAIc0lEQVR42u2d/2tV"
    "ZRzH92uIQ6epIZrMIjE1C0lJhBRd08HUFZP8klP8QjQhB2u6/M7UVqINpqAJKaFQ"
    "yVCQjSWZQcYksP6A8MegX/qtn5/2Xt6pY/fe55577nOe55zXDy8Y2+7dOZ/Pa5/z"
    "fL9VEyZMNABpoYogAEIDIDQAQgMgNCA0AEIDIDQAQgMgNCA0AEIDIDQAQgMgNCA0"
    "AEIDIDQAQgMgNCA0AEIDIDQAQgMgNCA0AEIDIDQAQgMgNCA0AEIDIDQAQgMgNCA0"
    "AEIDIDQAQgNCEwhAaACEBkBoAIQGhAZAaACEBkBoAIQGhIZYWLDgNdPeftAMDt41"
    "Dx78PoK+1vf0M2KE0F5TUzPV1NWtNZ2dR01f3+1RifOh39Hv6jV6LTFEaC+qcEvL"
    "LtPbe9EMDT0sKnE+9Fq9h96L6o3Q3lbhqFC9Edr7Kkz1RuhUV2GqN0KntgpTvRE6"
    "1VWY6o3QXlbhnGANDY0juPwHymr1rqIKu5coyX+utFfv1Am9fv27ZmDgx2Ae80k1"
    "fxQjxQqhPWbjxveCf5S7rt6KGUJ7yIwZM829e7+m6nHtonorZoodQntGT8+F1Heo"
    "KlW9FTuE9oiOjk8z12mKu3orhgjtAdu2tTCsFVP1ViwROkFWrapj6Crm6q2YInQC"
    "zJv3qrlz52erJJ082Z3pqWHde1dXt1WsFFPFFqEdUl09yVy9et0qQXv3fsQah8co"
    "FjYxU2wVY4R2xOnTX1gl5vjxU4g8BsXEJnaKMUI7oLX1Y6uEXL58NdHrnD53uZmz"
    "dLt5ZfUBM7+hawR9re/pZ0lem2JjE0PFGqErSFNTs1Ui+vvvmLlzX3Z6bRMnTTMv"
    "rWg1S3f3m/rT/5p1Z0xB9Dv6Xb1Gr3V5rYqNYmQTS8UcoSvAsmXLrXvqK1a87ey6"
    "Jk+rNQs39lhJXEhuvYfey9V1K0a28VTsETpGZs+eY27e7LcK/qZNW5xdl5oQ5Yg8"
    "nth6T1fXr1jZxFSxVw4QOiYuXPjKKvBtbZ84q8pqLsQl8lj03q6qtWJmE1vlAKFj"
    "4NChY1YBP3PmS2edvZUH/6yYzDn0N1x1HhU7mxgrFwhdBjt37rEK9PXr35spU553"
    "IvPqY39XXOYc+lsupFbsFEObWCsnCB2B+voG6+WPCxcudtLMcFGZx6vULpofiqHt"
    "8lvlBqEDD26xNnPbNWN6f/gffR13mzqLRSQVQvv4+NPIQz7ZmnqMGfjDmL/+eRZ9"
    "Tz+LS2pXox++NfOCF9q3Dooe94WG5saT+Wmp4xzSczXy4VtHPFihfRxC0oRHoWZG"
    "PplztJz4ycxvPDvCG9u+NSs7H0WWWteS1aHS4IT2cZBfU9KFqrPay8WE3t/RZZ6b"
    "OO0ZZi5uNm+1/hKpSruaJvd1MisIoX2dhtU6i0KCRRU6h6p2qVLrmrK+3MBroX1e"
    "KGMzslFM6FXvNOUVOorUrkY8QlgQ5qXQPi9ltFmnUahT+M13gwVlzlFK80PXxJJd"
    "T4X2ebG5ZuhsBMs3bCeZp86otRJabepSqnQS66lD2VSRmNC+bwfSQnzr2bzORyNN"
    "C7WXRbFmxniUMvqha2Pbm0dC79nzofcbNgtNpoxFw3GlCjwWvYdvkyzlbExWjjMh"
    "tA4IDGFLvbZM2Qqmjl25QpfSOdS1hXB0RBKHQToX2vZk0KQPPUHo8g/3Ua5TL7RN"
    "IE6d+jzx3jJNjsIoRza5ROhhbt0aSPywk1I7heUK7XuncGxbWjlC6BKaHDdu3DK1"
    "tckN1NsO2+XQ0FtUmUMYtsuhnCg3NDkidAq1RHHWrBeT22RQwgZYTY5EFdr3iZUc"
    "yoXt0t7MdArFli0fWAflypVrZvr0FxJJYKkbYaN0Dn2f+h59Yg3nQLmwzZtynKmJ"
    "lTVr6q2Dc+nS12by5CnOr7HY4qRypfZ9cdLomvDh2CsHtvlSbjM59b1uXaN1kM6f"
    "vzT8mmrnpyFFOXdDTYhCbeoQlo8+oXok9rZ5Uk4zvThpwwb7D/o5d67X/f7GAgv8"
    "bUY/NBwX4gL/HIq5bX6US9ZDD9Pc/L510Lq7z7p93BbZguUKl1uwcijWtnlRDlkP"
    "/RRbt263Dl5X12feTrJUCteTKYqxbT6UO3asjMOOHbutg3jkyAmvRzxCPMYgh2Jr"
    "mwfljD2FMSwrFQcOHHLa9EjzQTM5FFPb+Pv46QheHjSzb99+66C2tXU4nT1M41Fg"
    "T3bdd1jHXTnioJkUBDeNhzX6XERSdVijr4+/NB2n63MzL5XH6frcQQn9wHPfO+Kp"
    "PfDc5yGkUD+Swveh0lQLHcIgf0gfGuT7ZFYmhA5tGtbnj3XzfblBZoQObaGMj/i"
    "+ICxjQoe1lNE3Qliymzmhoyw2P3z4eOY/vF4xCGFTRSaFjrIdSPT13TadnUdNXd1"
    "aU1MzNbUC6950j7pX3XMpMUp621tmhS51w+ZYhoYemt7ei6alZVcqqrfuQfeie9K"
    "9RYlJ0huTMy90qVvq01S9y6nCvh4dgdCPWbTodevjEUKu3nFU4XzHDSiGaXChKi3"
    "txiVL3jT37/8WW5J9qN5xV+HxUMwUu7R4UJWmzlAps1++Vu9KVeH8s6qbU9Uhrkp"
    "bD1+Hm8TZ/Kh09XZRhfM1M5I4CAahPX5cR63erqtwloYsUyu0TxI1NDSO4OM/F0J"
    "Tvb0lK1UYoT2s3lRhhKZ6U4UROvTqTRVG6OCrN1UYoYOu3lRhhA6+elOFETq46t3"
    "eftAMDt4dlVhf63tUYYQGQGhAaACEBkBoAIQGQGhAaACEBkBoAIQGQGhAaACEBk"
    "BoAIQGQGhAaACEBkBoAIQGQGhAaACEBkBoAIQGQGhAaACEBkBoAIQGhAZAaACEBk"
    "BoAIQGhAZAaACEBkBoAIQGhAZAaACEBkBoAIQGhAZAaACEBkBogPH4D5W6MA4qD2"
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
    display: inline-flex; align-items: center; gap: 0.35rem;
    min-height: 28px; padding: 4px 6px;
    font-size: 13px; font-weight: 400; line-height: 1;
    background: transparent; color: rgba(230, 230, 230, 0.6);
    border: 0; border-radius: 7px;
    visibility: hidden; pointer-events: none;
    transition: background-color 120ms ease, color 120ms ease, transform 80ms ease;
  }
  #copy svg { width: 14px; height: 14px; stroke-width: 1.8; }
  #copy.show { visibility: visible; pointer-events: auto; }
  #copy:hover { background: rgba(255, 255, 255, 0.04); color: rgba(230, 230, 230, 0.86); }
  #copy:active { background: rgba(255, 255, 255, 0.03); transform: translateY(1px); }
  #copy:focus-visible { outline: 2px solid #4a8cff; outline-offset: 2px; }
  #copy.ok { color: #9ecf9e; }
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
    <button id="copy" type="button" aria-label="Copy summary">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true" focusable="false">
        <rect x="8" y="8" width="11" height="11" rx="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span class="copy-label">Copy</span>
    </button>
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
  const copyLabel = copy.querySelector('.copy-label');
  let es = null;

  function setCopyLabel(label) {
    copyLabel.textContent = label;
  }

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
    setCopyLabel('Copy');
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
      setCopyLabel('Copied');
      copy.classList.add('ok');
      setTimeout(() => {
        setCopyLabel('Copy');
        copy.classList.remove('ok');
      }, 1200);
    } catch {
      setCopyLabel('Copy failed');
      setTimeout(() => { setCopyLabel('Copy'); }, 1500);
    }
  });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


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
