import unittest

from app.prompts import (
    DEFAULT_PUBLICATION_GOAL,
    DEFAULT_TARGET_AUDIENCE,
    SYSTEM_PROMPT,
    VARIANT_STYLES,
    build_prompt,
    build_variant_prompt,
    build_variants_prompt,
)


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


class VariantStylesTests(unittest.TestCase):
    def test_contains_four_styles(self) -> None:
        self.assertEqual(
            list(VARIANT_STYLES.keys()),
            [
                "informational",
                "engaging",
                "practical",
                "analytical",
            ],
        )

    def test_every_style_has_label_and_description(self) -> None:
        for style, details in VARIANT_STYLES.items():
            with self.subTest(style=style):
                self.assertTrue(details["label"])
                self.assertTrue(details["description"])


class BuildVariantsPromptTests(unittest.TestCase):
    def test_prompt_contains_generation_parameters(self) -> None:
        prompt = build_variants_prompt(
            topic="ИИ в образовании",
            platform="Telegram",
            tone="дружелюбная",
            word_count=200,
            selected_styles=["informational", "engaging"],
        )

        self.assertIn("ИИ в образовании", prompt)
        self.assertIn("Telegram", prompt)
        self.assertIn("дружелюбная", prompt)
        self.assertIn("200", prompt)

    def test_prompt_contains_selected_styles(self) -> None:
        prompt = build_variants_prompt(
            topic="Тест",
            platform="VK",
            tone="нейтральная",
            word_count=100,
            selected_styles=["informational", "practical"],
        )

        self.assertIn("informational", prompt)
        self.assertIn("practical", prompt)
        self.assertNotIn('"engaging"', prompt)
        self.assertNotIn('"analytical"', prompt)

    def test_prompt_contains_style_descriptions(self) -> None:
        prompt = build_variants_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            selected_styles=["informational"],
        )

        self.assertIn(
            VARIANT_STYLES["informational"]["description"],
            prompt,
        )

    def test_prompt_explains_difference_between_style_and_tone(self) -> None:
        prompt = build_variants_prompt(
            topic="Тест",
            platform="Telegram",
            tone="дружелюбная",
            word_count=100,
            selected_styles=["informational"],
        )

        self.assertIn("Стили определяют способ подачи материала", prompt)
        self.assertIn("Не меняй выбранную тональность", prompt)

    def test_prompt_requires_json_response(self) -> None:
        prompt = build_variants_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            selected_styles=["informational"],
        )

        self.assertIn("корректный JSON", prompt)
        self.assertIn('"variants"', prompt)
        self.assertIn('"style"', prompt)
        self.assertIn('"text"', prompt)

    def test_prompt_forbids_fabricated_facts(self) -> None:
        prompt = build_variants_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            selected_styles=["informational"],
        )

        self.assertIn("Не придумывай факты", prompt)


class AdditionalGenerationSettingsPromptTests(unittest.TestCase):
    def test_prompt_contains_target_audience_and_its_guidance(self) -> None:
        prompt = build_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            target_audience="Начинающие",
        )

        self.assertIn("ЦЕЛЕВАЯ АУДИТОРИЯ:", prompt)
        self.assertIn("Начинающие", prompt)
        self.assertIn("только знакомится с темой", prompt)

    def test_prompt_contains_publication_goal_and_its_guidance(self) -> None:
        prompt = build_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            publication_goal="Продавать",
        )

        self.assertIn("ЦЕЛЬ ПУБЛИКАЦИИ:", prompt)
        self.assertIn("Продавать", prompt)
        self.assertIn("ценность предложения", prompt)

    def test_prompt_contains_additional_wishes(self) -> None:
        wishes = "Добавь пример из реальной жизни."

        prompt = build_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            additional_wishes=wishes,
        )

        self.assertIn("ДОПОЛНИТЕЛЬНЫЕ ПОЖЕЛАНИЯ ПОЛЬЗОВАТЕЛЯ:", prompt)
        self.assertIn(wishes, prompt)

    def test_empty_additional_wishes_are_omitted(self) -> None:
        prompt = build_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
            additional_wishes="   ",
        )

        self.assertNotIn("ДОПОЛНИТЕЛЬНЫЕ ПОЖЕЛАНИЯ", prompt)

    def test_defaults_preserve_general_audience_and_informational_goal(self) -> None:
        prompt = build_prompt(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=100,
        )

        self.assertIn(DEFAULT_TARGET_AUDIENCE, prompt)
        self.assertIn(DEFAULT_PUBLICATION_GOAL, prompt)

    def test_variant_prompt_receives_all_additional_settings(self) -> None:
        prompt = build_variant_prompt(
            topic="Тест",
            platform="VK",
            tone="дружелюбная",
            word_count=100,
            style="informational",
            target_audience="Эксперты",
            publication_goal="Провоцировать обсуждение",
            additional_wishes="Не используй эмодзи.",
        )

        self.assertIn("Эксперты", prompt)
        self.assertIn("Провоцировать обсуждение", prompt)
        self.assertIn("Не используй эмодзи.", prompt)

    def test_variants_prompt_receives_all_additional_settings(self) -> None:
        prompt = build_variants_prompt(
            topic="Тест",
            platform="VK",
            tone="дружелюбная",
            word_count=100,
            selected_styles=["informational"],
            target_audience="Специалисты",
            publication_goal="Вовлекать",
            additional_wishes="Добавь вопрос в начале.",
        )

        self.assertIn("Специалисты", prompt)
        self.assertIn("Вовлекать", prompt)
        self.assertIn("Добавь вопрос в начале.", prompt)

    def test_unknown_audience_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_prompt(
                "Тест",
                "Telegram",
                "нейтральная",
                100,
                target_audience="Неизвестная аудитория",
            )

    def test_unknown_goal_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_prompt(
                "Тест",
                "Telegram",
                "нейтральная",
                100,
                publication_goal="Неизвестная цель",
            )


if __name__ == "__main__":
    unittest.main()