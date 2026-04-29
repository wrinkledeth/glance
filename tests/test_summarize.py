import os
import unittest
from unittest.mock import patch

from glance.summarize import _stream_web, _system_prompt


class SystemPromptTests(unittest.TestCase):
    def test_article_prompt_requires_third_person_attribution(self) -> None:
        prompt = _system_prompt("article")

        self.assertIn("Write summaries in third person", prompt)
        self.assertIn('Do not say "you" to mean the reader', prompt)
        self.assertIn("the author argues", prompt)
        self.assertIn("the article says", prompt)

    def test_instagram_prompt_requires_comment_discussion(self) -> None:
        prompt = _system_prompt("instagram")

        self.assertIn("Instagram clips", prompt)
        self.assertIn("first-frame OCR overlay text", prompt)
        self.assertIn("may be noisy", prompt)
        self.assertIn("transcript", prompt)
        self.assertIn("top-comment discussion", prompt)

    def test_tiktok_prompt_avoids_inventing_when_transcript_missing(self) -> None:
        prompt = _system_prompt("tiktok")

        self.assertIn("TikTok videos", prompt)
        self.assertIn("first-frame OCR overlay text", prompt)
        self.assertIn("may be noisy", prompt)
        self.assertIn("transcript", prompt)
        self.assertIn("do not invent spoken words or visual details", prompt)


class WebStreamTests(unittest.TestCase):
    def test_stream_web_reports_remote_model_progress(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def raise_for_status(self) -> None:
                return None

            def iter_lines(self):
                yield '{"meta":{"provider":"ollama","model":"qwen-test"}}'
                yield '{"chunk":"hello"}'
                yield '{"done":true}'

        events: list[str] = []
        with (
            patch.dict(os.environ, {"GLANCE_WEB_URL": "http://remote"}, clear=False),
            patch("glance.summarize.httpx.stream", return_value=FakeResponse()),
        ):
            chunks = list(_stream_web("content", "system", progress=events.append))

        self.assertEqual(events, ["summarizing with ollama / qwen-test"])
        self.assertEqual(chunks, ["hello"])


if __name__ == "__main__":
    unittest.main()
