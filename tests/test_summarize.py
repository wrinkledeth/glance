import unittest

from glance.summarize import _system_prompt


class SystemPromptTests(unittest.TestCase):
    def test_article_prompt_requires_third_person_attribution(self) -> None:
        prompt = _system_prompt("article")

        self.assertIn("Write summaries in third person", prompt)
        self.assertIn('Do not say "you" to mean the reader', prompt)
        self.assertIn("the author argues", prompt)
        self.assertIn("the article says", prompt)


if __name__ == "__main__":
    unittest.main()
