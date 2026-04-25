import json
import os
import sys

from dotenv import load_dotenv
import anthropic
import httpx

load_dotenv()

ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


def _system_prompt(source_type: str) -> str:
    if source_type == "youtube":
        return "You summarize YouTube video transcripts. Give a clear, concise summary of the key points. Use bullet points for the main ideas. Keep it under 300 words."
    if source_type == "reddit":
        return "You summarize Reddit threads. Summarize the post and the general sentiment/key points from the comments. Use bullet points. Keep it under 300 words."
    if source_type == "twitter":
        return "You summarize tweets and Twitter/X threads. Give a clear, concise summary of the key points and any notable context. Use bullet points. Keep it under 200 words."
    return "Summarize the following content concisely using bullet points."


def _summarize_anthropic(content: str, system: str) -> str:
    print(f"→ anthropic / {ANTHROPIC_MODEL}", file=sys.stderr, flush=True)
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return message.content[0].text


def _summarize_ollama(content: str, system: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:35B-A3B")
    print(f"→ ollama / {model}", file=sys.stderr, flush=True)

    parts: list[str] = []
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
                parts.append(chunk)
                sys.stderr.write(chunk)
                sys.stderr.flush()
            if obj.get("done"):
                break

    sys.stderr.write("\n")
    sys.stderr.flush()
    return "".join(parts)


def summarize(content: str, source_type: str, provider: str | None = None) -> str:
    """Summarize content using the configured LLM provider."""
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "anthropic")

    system = _system_prompt(source_type)

    if provider == "anthropic":
        return _summarize_anthropic(content, system)
    if provider == "ollama":
        return _summarize_ollama(content, system)
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'anthropic' or 'ollama')")
