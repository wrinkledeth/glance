# glance

Summarize threads / videos without exposing yourself to toxic algos.

Supported sites:
- Youtube
- Reddit
- Twitter / X

## Why

You want the information, not the platform. Glance fetches content headlessly and pipes it through Claude for a summary. This lets you keep your content blockers up forever, you never need to open a browser tab.

## How it works

1. Paste a URL into the CLI
2. Glance detects the source (YouTube, Reddit, or Twitter/X)
3. Fetches content headlessly — `yt-dlp` for transcripts, Reddit's JSON API for threads, Twitter's oEmbed API for tweets
4. Pipes it to Claude for a summary
5. Prints the summary to your terminal

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone and install
git clone <repo-url>
cd glance
uv sync

# Install yt-dlp (needed for YouTube)
uv tool install yt-dlp

# Set up your API key
cp .env.example .env
# Edit .env with your Anthropic API key
```

## Usage

```bash
# Summarize an X post
uv run glance "https://x.com/MilkRoadAI/status/2033929705028517963"

Fetching twitter content...
Summarizing...
**Key Points:**

• Someone created an entirely fake band using AI tools and successfully fooled 80,000 listeners on Spotify

• **AI Tools Used:**
  - Suno AI to generate realistic-sounding songs
  - AI-generated music videos featuring fake band members with synthetic faces
  - Created fictional backstories and biographies for the fake musicians

• The deception was sophisticated enough that thousands of people couldn't distinguish the AI-generated content from real music

• Demonstrates the advanced state of AI music generation and deepfake technology

**Notable Context:**
This highlights growing concerns about AI's ability to create convincing fake content in the entertainment industry. The scale of the deception (80k followers) shows how AI-generated
  music could potentially disrupt the music industry, raising questions about authenticity, artist compensation, and platform verification. The tweet appears to be from March 2026,
  suggesting this is either a future projection or the date may be incorrect.
```

## Project structure

```
glance/
├── pyproject.toml            # Project config and dependencies
├── .env.example              # API key template
├── src/glance/
│   ├── cli.py                # Entry point, URL detection
│   ├── youtube.py            # yt-dlp transcript extraction
│   ├── reddit.py             # Reddit JSON thread fetching
│   ├── twitter.py            # Twitter/X oEmbed fetching
│   └── summarize.py          # Claude API summarization
```

## Future ideas

- MCP server so you can call it from Claude directly
- More sources (HN, articles)
- Configurable summary length/style
- Local LLM support


