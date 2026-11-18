import json
import unittest
from unittest.mock import MagicMock, patch

import httpx
from gigachat.exceptions import (
    AuthenticationError,
    RateLimitError,
    ServerError,
)

from app.config import (
    TEMPERATURE,
    TOP_P,
    REPETITION_PENALTY,
    MAX_TOKENS,
    MAX_REVISION_ATTEMPTS,
    WORD_COUNT_TOLERANCE,
)
from app.generator import (
    ContentGenerationError,
    _get_word_count_limits,
    _parse_variants_response,
    _request_gigachat,
    count_words,
    generate_content,
    generate_variants,
)
from app.prompts import (
    DEFAULT_PUBLICATION_GOAL,
    DEFAULT_TARGET_AUDIENCE,
    PUBLICATION_GOALS,
    TARGET_AUDIENCES,
    VARIANT_STYLES,
)


def fake_response(content: str) -> MagicMock:
    """Создаёт имитацию ответа GigaChat с указанным текстом."""

    response = MagicMock()
    response.choices[0].message.content = content
    return response


def make_text(word_count: int) -> str:
    """Создаёт тестовый текст с заданным количеством слов."""

    return " ".join(["слово"] * word_count)


def make_variants_response(
    styles: list[str],
    word_count: int = 40,
) -> str:
    """Создаёт JSON с вариантами заданных стилей."""

    return json.dumps(
        {
            "variants": [
                {
                    "style": style,
                    "text": make_text(word_count),
                }
                for style in styles
            ]
        },
        ensure_ascii=False,
    )


class CountWordsTests(unittest.TestCase):
    def test_counts_russian_words(self) -> None:
        self.assertEqual(
            count_words("Искусственный интеллект меняет образование"),
            4,
        )

    def test_counts_english_words(self) -> None:
        self.assertEqual(
            count_words("Artificial intelligence changes education"),
            4,
        )

    def test_counts_hyphenated_words_as_one(self) -> None:
        self.assertEqual(
            count_words("Научно-технический и социально-экономический"),
            3,
        )

    def test_counts_apostrophe_words_as_one(self) -> None:
        self.assertEqual(
            count_words("Don't stop learning"),
            3,
        )

    def test_ignores_numbers_and_punctuation(self) -> None:
        self.assertEqual(
            count_words("1. Пример текста: 2026 год, 100% результата!"),
            4,
        )

    def test_returns_zero_for_empty_text(self) -> None:
        self.assertEqual(count_words(""), 0)


class WordCountLimitsTests(unittest.TestCase):
    def test_tolerance_is_twenty_percent(self) -> None:
        self.assertEqual(WORD_COUNT_TOLERANCE, 0.2)

    def test_returns_expected_limits(self) -> None:
        self.assertEqual(_get_word_count_limits(40), (32, 48))

    def test_rounds_limits_to_integer_values(self) -> None:
        self.assertEqual(_get_word_count_limits(33), (27, 39))

class RequestGigaChatTests(unittest.TestCase):
    def test_raises_error_when_credentials_are_missing(self) -> None:
        with (
            patch("app.generator.GIGACHAT_CREDENTIALS", None),
            patch("app.generator.GigaChat") as giga_chat,
        ):
            with self.assertRaisesRegex(
                ContentGenerationError,
                "GIGACHAT_CREDENTIALS",
            ):
                _request_gigachat([])

        giga_chat.assert_not_called()

class GenerateContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_patch = patch("app.generator.GigaChat")
        self.giga_class = self.client_patch.start()
        self.client = self.giga_class.return_value.__enter__.return_value
        self.addCleanup(self.client_patch.stop)

    def test_returns_generated_text_within_allowed_range(self) -> None:
        expected_text = make_text(40)
        self.client.chat.return_value = fake_response(expected_text)

        text = generate_content(
            "ИИ в образовании",
            "Telegram",
            "дружелюбная",
            40,
        )

        self.assertEqual(text, expected_text)
        self.client.chat.assert_called_once()

    def test_accepts_minimum_allowed_word_count(self) -> None:
        self.client.chat.return_value = fake_response(make_text(32))

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 32)
        self.client.chat.assert_called_once()

    def test_accepts_maximum_allowed_word_count(self) -> None:
        self.client.chat.return_value = fake_response(make_text(48))

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 48)
        self.client.chat.assert_called_once()

    def test_strips_whitespace_from_generated_text(self) -> None:
        expected_text = make_text(40)
        self.client.chat.return_value = fake_response(
            f"  \n{expected_text}\n  "
        )

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(text, expected_text)

    def test_passes_generation_parameters(self) -> None:
        self.client.chat.return_value = fake_response(make_text(40))

        with patch("app.generator.Chat") as chat_model:
            generate_content("Тест", "Telegram", "нейтральная", 40)

        chat_model.assert_called_once()
        parameters = chat_model.call_args.kwargs

        self.assertEqual(parameters["temperature"], TEMPERATURE)
        self.assertEqual(parameters["top_p"], TOP_P)
        self.assertEqual(
            parameters["repetition_penalty"],
            REPETITION_PENALTY,
        )
        self.assertEqual(parameters["max_tokens"], MAX_TOKENS)

    def test_corrects_text_that_is_too_short(self) -> None:
        self.client.chat.side_effect = [
            fake_response(make_text(30)),
            fake_response(make_text(40)),
        ]

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(text, make_text(40))
        self.assertEqual(self.client.chat.call_count, 2)

    def test_corrects_text_that_is_too_long(self) -> None:
        self.client.chat.side_effect = [
            fake_response(make_text(50)),
            fake_response(make_text(40)),
        ]

        text = generate_content("Тест", "VK", "профессиональная", 40)

        self.assertEqual(text, make_text(40))
        self.assertEqual(self.client.chat.call_count, 2)

    def test_uses_multiple_correction_attempts_if_needed(self) -> None:
        self.client.chat.side_effect = [
            fake_response(make_text(25)),
            fake_response(make_text(30)),
            fake_response(make_text(40)),
        ]

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 40)
        self.assertEqual(
            self.client.chat.call_count,
            MAX_REVISION_ATTEMPTS + 1,
        )

    def test_returns_last_result_after_all_attempts(self) -> None:
        self.client.chat.side_effect = [
            fake_response(make_text(25)),
            fake_response(make_text(28)),
            fake_response(make_text(30)),
        ]

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 30)
        self.assertEqual(
            self.client.chat.call_count,
            MAX_REVISION_ATTEMPTS + 1,
        )

    def test_raises_for_empty_choices(self) -> None:
        response = fake_response(make_text(40))
        response.choices = []
        self.client.chat.return_value = response

        with self.assertRaisesRegex(
            ContentGenerationError,
            "вариантов ответа",
        ):
            generate_content("Тест", "Telegram", "нейтральная", 40)

    def test_raises_for_empty_text(self) -> None:
        self.client.chat.return_value = fake_response("")

        with self.assertRaisesRegex(
            ContentGenerationError,
            "пустой текст",
        ):
            generate_content("Тест", "Telegram", "нейтральная", 40)

    def test_raises_for_whitespace_only_text(self) -> None:
        self.client.chat.return_value = fake_response(" \n\t ")

        with self.assertRaises(ContentGenerationError):
            generate_content("Тест", "VK", "нейтральная", 40)

    def test_handles_authentication_error(self) -> None:
        self.client.chat.side_effect = AuthenticationError(
            "https://gigachat.example",
            401,
            b"Unauthorized",
            None,
        )

        with self.assertRaisesRegex(
            ContentGenerationError,
            "авторизоваться",
        ):
            generate_content("Тест", "Telegram", "нейтральная", 40)

    def test_handles_rate_limit_error(self) -> None:
        self.client.chat.side_effect = RateLimitError(
            "https://gigachat.example",
            429,
            b"Too Many Requests",
            httpx.Headers({"retry-after": "30"}),
        )

        with self.assertRaisesRegex(ContentGenerationError, "30 сек"):
            generate_content("Тест", "Telegram", "нейтральная", 40)

    def test_handles_server_error(self) -> None:
        self.client.chat.side_effect = ServerError(
            "https://gigachat.example",
            500,
            b"Internal Server Error",
            None,
        )

        with self.assertRaisesRegex(ContentGenerationError, "ошибка"):
            generate_content("Тест", "Telegram", "нейтральная", 40)

    def test_handles_connection_timeout(self) -> None:
        self.client.chat.side_effect = httpx.TimeoutException(
            "Connection timed out"
        )

        with self.assertRaisesRegex(
            ContentGenerationError,
            "время ожидания",
        ):
            generate_content("Тест", "Telegram", "нейтральная", 40)


class ParseVariantsResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.styles = ["informational", "engaging"]

    def test_parses_valid_json(self) -> None:
        response = make_variants_response(self.styles)

        variants = _parse_variants_response(response, self.styles)

        self.assertEqual(list(variants.keys()), self.styles)
        self.assertEqual(count_words(variants["informational"]), 40)
        self.assertEqual(count_words(variants["engaging"]), 40)

    def test_parses_json_inside_markdown_code_block(self) -> None:
        response = (
            "```json\n"
            f"{make_variants_response(self.styles)}\n"
            "```"
        )

        variants = _parse_variants_response(response, self.styles)

        self.assertEqual(len(variants), 2)

    def test_raises_for_invalid_json(self) -> None:
        with self.assertRaisesRegex(
            ContentGenerationError,
            "неправильном формате",
        ):
            _parse_variants_response("Это не JSON", self.styles)

    def test_raises_when_variants_list_is_missing(self) -> None:
        response = json.dumps({"items": []})

        with self.assertRaises(ContentGenerationError):
            _parse_variants_response(response, self.styles)

    def test_raises_for_wrong_number_of_variants(self) -> None:
        response = make_variants_response(["informational"])

        with self.assertRaisesRegex(ContentGenerationError, "количество"):
            _parse_variants_response(response, self.styles)

    def test_raises_for_unknown_style(self) -> None:
        response = make_variants_response(["informational", "unknown"])

        with self.assertRaisesRegex(ContentGenerationError, "неизвестный"):
            _parse_variants_response(response, self.styles)

    def test_raises_for_duplicate_style(self) -> None:
        response = make_variants_response(
            ["informational", "informational"]
        )

        with self.assertRaisesRegex(
            ContentGenerationError,
            "несколько вариантов",
        ):
            _parse_variants_response(response, self.styles)

    def test_raises_for_empty_variant_text(self) -> None:
        response = json.dumps(
            {
                "variants": [
                    {"style": "informational", "text": ""},
                    {"style": "engaging", "text": make_text(40)},
                ]
            }
        )

        with self.assertRaisesRegex(ContentGenerationError, "не пустым"):
            _parse_variants_response(response, self.styles)


class GenerateVariantsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request_patch = patch("app.generator._request_gigachat")
        self.mock_request = self.request_patch.start()
        self.addCleanup(self.request_patch.stop)

    def test_generates_four_variants_by_default(self) -> None:
        self.mock_request.return_value = make_text(40)

        variants = generate_variants(
            topic="ИИ в образовании",
            platform="Telegram",
            tone="дружелюбная",
            word_count=40,
        )

        styles = list(VARIANT_STYLES.keys())

        self.assertEqual(len(variants), 4)
        self.assertEqual(
            [variant["style"] for variant in variants],
            styles,
        )
        self.assertEqual(self.mock_request.call_count, 4)

    def test_generates_requested_number_of_variants(self) -> None:
        self.mock_request.return_value = make_text(40)

        variants = generate_variants(
            topic="ИИ в образовании",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=2,
        )

        self.assertEqual(len(variants), 2)
        self.assertEqual(
            [variant["style"] for variant in variants],
            ["informational", "engaging"],
        )
        self.assertEqual(self.mock_request.call_count, 2)

    def test_returns_variant_metadata_and_word_count(self) -> None:
        self.mock_request.return_value = make_text(40)

        variants = generate_variants(
            topic="Тест",
            platform="VK",
            tone="нейтральная",
            word_count=40,
            variant_count=1,
        )

        variant = variants[0]

        self.assertEqual(variant["style"], "informational")
        self.assertEqual(
            variant["label"],
            VARIANT_STYLES["informational"]["label"],
        )
        self.assertEqual(
            variant["description"],
            VARIANT_STYLES["informational"]["description"],
        )
        self.assertEqual(variant["word_count"], 40)
        self.assertTrue(variant["is_valid"])
        self.assertEqual(variant["min_word_count"], 32)
        self.assertEqual(variant["max_word_count"], 48)
        self.assertEqual(count_words(variant["text"]), 40)
        self.mock_request.assert_called_once()

    def test_accepts_word_count_at_lower_boundary(self) -> None:
        self.mock_request.return_value = make_text(32)

        variants = generate_variants(
            "Тест",
            "Telegram",
            "нейтральная",
            40,
            1,
        )

        self.assertTrue(variants[0]["is_valid"])
        self.assertEqual(variants[0]["word_count"], 32)
        self.assertEqual(self.mock_request.call_count, 1)

    def test_accepts_word_count_at_upper_boundary(self) -> None:
        self.mock_request.return_value = make_text(48)

        variants = generate_variants(
            "Тест",
            "Telegram",
            "нейтральная",
            40,
            1,
        )

        self.assertTrue(variants[0]["is_valid"])
        self.assertEqual(variants[0]["word_count"], 48)
        self.assertEqual(self.mock_request.call_count, 1)

    def test_corrects_each_variant_independently(self) -> None:
        self.mock_request.side_effect = [
            make_text(30),
            make_text(40),
            make_text(30),
            make_text(40),
        ]

        variants = generate_variants(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=2,
        )

        self.assertEqual(len(variants), 2)
        self.assertEqual(
            [variant["word_count"] for variant in variants],
            [40, 40],
        )
        self.assertTrue(all(variant["is_valid"] for variant in variants))
        self.assertEqual(self.mock_request.call_count, 4)

    def test_returns_inaccurate_variant_instead_of_raising(self) -> None:
        self.mock_request.side_effect = [
            make_text(20),
            make_text(25),
            make_text(30),
        ]

        variants = generate_variants(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=1,
        )

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["word_count"], 30)
        self.assertFalse(variants[0]["is_valid"])
        self.assertEqual(variants[0]["min_word_count"], 32)
        self.assertEqual(variants[0]["max_word_count"], 48)
        self.assertEqual(self.mock_request.call_count, 3)

    def test_inaccurate_variant_does_not_stop_other_variants(self) -> None:
        self.mock_request.side_effect = [
            make_text(20),
            make_text(25),
            make_text(30),
            make_text(40),
        ]

        variants = generate_variants(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=2,
        )

        self.assertEqual(len(variants), 2)
        self.assertFalse(variants[0]["is_valid"])
        self.assertTrue(variants[1]["is_valid"])
        self.assertEqual(self.mock_request.call_count, 4)

    def test_uses_default_audience_and_goal(self) -> None:
        self.mock_request.return_value = make_text(40)

        generate_variants(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=1,
        )

        prompt = self.mock_request.call_args.kwargs["messages"][1].content

        self.assertIn(DEFAULT_TARGET_AUDIENCE, prompt)
        self.assertIn(DEFAULT_PUBLICATION_GOAL, prompt)

    def test_passes_new_settings_to_generation_prompt(self) -> None:
        self.mock_request.return_value = make_text(40)

        generate_variants(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=1,
            target_audience="Специалисты",
            publication_goal="Вовлекать",
            additional_wishes="Добавь практический пример.",
        )

        prompt = self.mock_request.call_args.kwargs["messages"][1].content

        self.assertIn("Специалисты", prompt)
        self.assertIn("Вовлекать", prompt)
        self.assertIn("Добавь практический пример.", prompt)

    def test_passes_new_settings_to_correction_prompt(self) -> None:
        self.mock_request.side_effect = [
            make_text(20),
            make_text(40),
        ]

        generate_variants(
            topic="Тест",
            platform="Telegram",
            tone="нейтральная",
            word_count=40,
            variant_count=1,
            target_audience="Эксперты",
            publication_goal="Информировать",
            additional_wishes="Используй точные формулировки.",
        )

        correction_prompt = (
            self.mock_request.call_args_list[1]
            .kwargs["messages"][1]
            .content
        )

        self.assertIn("Эксперты", correction_prompt)
        self.assertIn("Информировать", correction_prompt)
        self.assertIn(
            "Используй точные формулировки.",
            correction_prompt,
        )

    def test_rejects_invalid_target_audience(self) -> None:
        with self.assertRaises(ValueError):
            generate_variants(
                "Тест",
                "Telegram",
                "нейтральная",
                40,
                target_audience="Несуществующая аудитория",
            )

    def test_rejects_invalid_publication_goal(self) -> None:
        with self.assertRaises(ValueError):
            generate_variants(
                "Тест",
                "Telegram",
                "нейтральная",
                40,
                publication_goal="Несуществующая цель",
            )

    def test_accepts_all_supported_audiences(self) -> None:
        self.mock_request.return_value = make_text(40)

        for audience in TARGET_AUDIENCES:
            with self.subTest(audience=audience):
                self.mock_request.reset_mock()

                generate_variants(
                    "Тест",
                    "Telegram",
                    "нейтральная",
                    40,
                    variant_count=1,
                    target_audience=audience,
                )

                self.mock_request.assert_called_once()

    def test_accepts_all_supported_goals(self) -> None:
        self.mock_request.return_value = make_text(40)

        for goal in PUBLICATION_GOALS:
            with self.subTest(goal=goal):
                self.mock_request.reset_mock()

                generate_variants(
                    "Тест",
                    "Telegram",
                    "нейтральная",
                    40,
                    variant_count=1,
                    publication_goal=goal,
                )

                self.mock_request.assert_called_once()

    def test_rejects_empty_topic(self) -> None:
        with self.assertRaises(ValueError):
            generate_variants("", "Telegram", "нейтральная", 40)

    def test_rejects_non_positive_word_count(self) -> None:
        with self.assertRaises(ValueError):
            generate_variants("Тест", "Telegram", "нейтральная", 0)

    def test_rejects_invalid_variant_count(self) -> None:
        for variant_count in (0, 5):
            with self.subTest(variant_count=variant_count):
                with self.assertRaises(ValueError):
                    generate_variants(
                        "Тест",
                        "Telegram",
                        "нейтральная",
                        40,
                        variant_count,
                    )

    def test_propagates_api_error(self) -> None:
        self.mock_request.side_effect = ContentGenerationError(
            "Ошибка GigaChat"
        )

        with self.assertRaisesRegex(ContentGenerationError, "GigaChat"):
            generate_variants(
                "Тест",
                "Telegram",
                "нейтральная",
                40,
                1,
            )


if __name__ == "__main__":
    unittest.main()