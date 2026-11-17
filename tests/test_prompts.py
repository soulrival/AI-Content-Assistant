
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

    def test_prompt_contains_all_parameter_labels(self) -> None:
        prompt = build_prompt(
            topic="Тестовая тема",
            platform="VK",
            tone="нейтральная",
            word_count=100,
        )

        self.assertIn("ТЕМА:", prompt)
        self.assertIn("ПЛОЩАДКА:", prompt)
        self.assertIn("ТОНАЛЬНОСТЬ:", prompt)
        self.assertIn("ЖЕЛАЕМЫЙ ОБЪЁМ:", prompt)

    def test_system_prompt_is_not_empty(self) -> None:
        self.assertTrue(SYSTEM_PROMPT.strip())

    def test_system_prompt_contains_content_requirements(self) -> None:
        required_instructions = (
            "Строго придерживайся заданной темы",
            "Не придумывай факты",
            "Избегай шаблонных вступлений",
            "Соблюдай указанный объём",
            "Верни только готовую публикацию",
        )

        for instruction in required_instructions:
            with self.subTest(instruction=instruction):
                self.assertIn(instruction, SYSTEM_PROMPT)

    def test_system_prompt_contains_platform_guidelines(self) -> None:
        self.assertIn("Telegram:", SYSTEM_PROMPT)
        self.assertIn("VK:", SYSTEM_PROMPT)

    def test_system_prompt_contains_tone_guidelines(self) -> None:
        self.assertIn("Нейтральная:", SYSTEM_PROMPT)
        self.assertIn("Дружелюбная:", SYSTEM_PROMPT)
        self.assertIn("Профессиональная:", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
