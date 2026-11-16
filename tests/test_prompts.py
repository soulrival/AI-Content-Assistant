import unittest

from app.prompts import SYSTEM_PROMPT, build_prompt


class BuildPromptTests(unittest.TestCase):
    def test_prompt_contains_topic_platform_tone_and_word_count(self) -> None:
        prompt = build_prompt(
            topic="ИИ в образовании",
            platform="Telegram",
            tone="дружелюбная",
            word_count=200,
        )

        self.assertIn("ИИ в образовании", prompt)
        self.assertIn("Telegram", prompt)
        self.assertIn("дружелюбная", prompt)
        self.assertIn("200", prompt)

    def test_system_prompt_is_not_empty(self) -> None:
        self.assertTrue(SYSTEM_PROMPT.strip())


if __name__ == "__main__":
    unittest.main()
