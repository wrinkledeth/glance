from dotenv import load_dotenv
import anthropic

load_dotenv()


def summarize(content: str, source_type: str) -> str:
    """Summarize content using Claude."""
    client = anthropic.Anthropic()

    if source_type == "youtube":
        system = "You summarize YouTube video transcripts. Give a clear, concise summary of the key points. Use bullet points for the main ideas. Keep it under 300 words."
    elif source_type == "reddit":
        system = "You summarize Reddit threads. Summarize the post and the general sentiment/key points from the comments. Use bullet points. Keep it under 300 words."
    else:
        system = "Summarize the following content concisely using bullet points."

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": content}],
    )

    return message.content[0].text
