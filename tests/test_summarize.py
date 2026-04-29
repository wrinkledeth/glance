import unittest

from glance.summarize import _system_prompt


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
        self.assertIn("transcript", prompt)
        self.assertIn("top-comment discussion", prompt)

    def test_tiktok_prompt_avoids_inventing_when_transcript_missing(self) -> None:
        prompt = _system_prompt("tiktok")

        self.assertIn("TikTok videos", prompt)
        self.assertIn("transcript", prompt)
        self.assertIn("do not invent spoken words or visual details", prompt)


if __name__ == "__main__":
    unittest.main()
