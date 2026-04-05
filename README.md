# glance

Summarize YouTube videos, Reddit threads, and X posts — without exposing yourself to the algorithm.

No browser tab. No autoplay. No "recommended for you." Just the content you asked for.

## How it works

Paste a URL → glance fetches content headlessly → Claude summarizes it → printed to your terminal.

- **YouTube** — transcript via `yt-dlp`
- **Reddit** — thread via JSON API  
- **X / Twitter** — tweet via oEmbed API

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).
```bash
git clone <repo-url> && cd glance
uv sync
uv tool install yt-dlp        # needed for YouTube
cp .env.example .env          # add your Anthropic API key
```

## Usage
```bash
uv run glance "https://x.com/MilkRoadAI/status/2033929705028517963"
```

```md
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
## Structure
```
src/glance/
├── cli.py          # entry point, URL detection
├── youtube.py      # yt-dlp transcript extraction
├── reddit.py       # Reddit JSON thread fetching
├── twitter.py      # Twitter/X oEmbed fetching
└── summarize.py    # Claude API summarization
```
