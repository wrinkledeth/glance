import json
import os
import sys
from datetime import date
from typing import Iterator

from dotenv import load_dotenv
import anthropic
import httpx

load_dotenv()

ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


def _system_prompt(source_type: str) -> str:
    today = date.today().isoformat()
    header = (
        f"Today's date is {today}. Use it to flag content that is stale, time-sensitive, "
        "or references events relative to now.\n\n"
        "Format every response as:\n"
        "1. A single-line **TL;DR:** (one sentence, no bullets).\n"
        "2. A blank line.\n"
        "3. Bullet points for the details.\n\n"
    )
    if source_type == "youtube":
        return header + (
            "You summarize YouTube video transcripts. Capture the core argument or "
            "narrative, then the key supporting points. Skip filler, sponsor reads, "
            "and intros. Keep the bullets under 300 words total."
        )
    if source_type == "reddit":
        return header + (
            "You summarize Reddit threads. Cover what the post is about, then the "
            "main threads of discussion and overall sentiment in the comments. Note "
            "if top comments disagree with the post. Keep the bullets under 300 words total."
        )
    if source_type == "twitter":
        return header + (
            "You summarize tweets and X threads. Capture the claim or story, any "
            "notable context (who is speaking, what they're responding to), and the "
            "tone. Keep the bullets under 200 words total."
        )
    if source_type == "article":
        return header + (
            "You summarize articles (blog posts, news, essays). Capture the thesis, "
            "then the supporting points or evidence. Note the author's stance if "
            "it's an opinion piece. Skip nav/footer noise. Keep the bullets under "
            "300 words total."
        )
    if source_type == "hn":
        return (
            f"Today's date is {today}. Use it to flag content that is stale, "
            "time-sensitive, or references events relative to now.\n\n"
            "You summarize Hacker News submissions. The input has an "
            "`=== Article ===` section (the linked piece, if any) and a "
            "`=== Discussion ===` section (top comments in HN's display order). "
            "Format your response as:\n"
            "1. A single-line **TL;DR:** (one sentence covering both article and discussion).\n"
            "2. A blank line.\n"
            "3. **Article** subsection with bullets on the article's substance. "
            "Omit this subsection entirely if the input says the article was not "
            "fetched or unavailable.\n"
            "4. A blank line.\n"
            "5. **Discussion** subsection with bullets on what HN is debating, "
            "top counterpoints, and overall sentiment.\n\n"
            "Keep the total under 400 words."
        )
    return header + "Summarize the following content concisely."


def resolve_model(provider: str | None = None) -> tuple[str, str]:
    """Return (provider, model) for the given (or env-configured) provider.

    For the 'web' provider the model is unknown locally (the remote decides),
    so we return a sentinel string. Callers using this for cache keys should
    treat 'web' as opaque or query the remote separately.
    """
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        return provider, ANTHROPIC_MODEL
    if provider == "ollama":
        return provider, os.getenv("OLLAMA_MODEL", "qwen3.5:35B-A3B")
    if provider == "web":
        return provider, "remote"
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def _stream_anthropic(content: str, system: str) -> Iterator[str]:
    print(f"→ anthropic / {ANTHROPIC_MODEL}", file=sys.stderr, flush=True)
    client = anthropic.Anthropic()
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def _parse_keep_alive(raw: str) -> int | str:
    try:
        return int(raw)
    except ValueError:
        return raw


def _format_ollama_stats(done: dict) -> str | None:
    parts: list[str] = []

    load_ns = done.get("load_duration") or 0
    if load_ns >= 50_000_000:
        parts.append(f"      load    {load_ns / 1e9:>6.2f}s")

    pcount = done.get("prompt_eval_count") or 0
    pdur_ns = done.get("prompt_eval_duration") or 0
    if pcount and pdur_ns:
        pdur = pdur_ns / 1e9
        parts.append(
            f"      prompt  {pcount:>5d} tok in {pdur:>5.2f}s  =  "
            f"{pcount / pdur:>6.1f} tok/s"
        )

    ocount = done.get("eval_count") or 0
    odur_ns = done.get("eval_duration") or 0
    if ocount and odur_ns:
        odur = odur_ns / 1e9
        parts.append(
            f"      output  {ocount:>5d} tok in {odur:>5.2f}s  =  "
            f"{ocount / odur:>6.1f} tok/s"
        )

    total_ns = done.get("total_duration") or 0
    if total_ns:
        parts.append(f"      total                         {total_ns / 1e9:>6.2f}s")

    if not parts:
        return None
    return "  ↳ ollama stats\n" + "\n".join(parts)


def _stream_ollama(content: str, system: str) -> Iterator[str]:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:35B-A3B")
    keep_alive = _parse_keep_alive(os.getenv("GLANCE_OLLAMA_KEEP_ALIVE", "0"))
    print(f"→ ollama / {model}", file=sys.stderr, flush=True)

    done_obj: dict | None = None
    with httpx.stream(
        "POST",
        f"{host.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "stream": True,
            "think": False,
            "keep_alive": keep_alive,
        },
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            obj = json.loads(line)
            chunk = obj.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if obj.get("done"):
                done_obj = obj
                break

    if done_obj is not None:
        stats = _format_ollama_stats(done_obj)
        if stats:
            print(stats, file=sys.stderr, flush=True)


def _stream_web(content: str, system: str) -> Iterator[str]:
    base = os.getenv("GLANCE_WEB_URL")
    if not base:
        raise RuntimeError("GLANCE_WEB_URL not set (e.g. http://moodylotus:8765)")
    print(f"→ web / {base}", file=sys.stderr, flush=True)

    with httpx.stream(
        "POST",
        f"{base.rstrip('/')}/llm",
        json={"content": content, "system": system},
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            obj = json.loads(line)
            if "error" in obj:
                raise RuntimeError(obj["error"])
            if "meta" in obj:
                meta = obj["meta"]
                print(
                    f"  ↳ remote: {meta.get('provider', '?')} / {meta.get('model', '?')}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            chunk = obj.get("chunk", "")
            if chunk:
                yield chunk
            if obj.get("done"):
                break


def summarize_stream(content: str, source_type: str, provider: str | None = None) -> Iterator[str]:
    """Stream summary chunks from the configured LLM provider."""
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "anthropic")

    system = _system_prompt(source_type)

    if provider == "anthropic":
        return _stream_anthropic(content, system)
    if provider == "ollama":
        return _stream_ollama(content, system)
    if provider == "web":
        return _stream_web(content, system)
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'anthropic', 'ollama', or 'web')")


def summarize(content: str, source_type: str, provider: str | None = None) -> str:
    """Summarize content using the configured LLM provider."""
    resolved = provider or os.getenv("LLM_PROVIDER", "anthropic")
    echo = resolved in {"ollama", "web"}

    parts: list[str] = []
    for chunk in summarize_stream(content, source_type, provider):
        parts.append(chunk)
        if echo:
            sys.stderr.write(chunk)
            sys.stderr.flush()
    if echo:
        sys.stderr.write("\n")
        sys.stderr.flush()
    return "".join(parts)
