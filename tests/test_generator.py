
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
)
from app.generator import (
    ContentGenerationError,
    count_words,
    generate_content,
)


def fake_response(content: str) -> MagicMock:
    """Создаёт имитацию ответа GigaChat с указанным текстом."""
    response = MagicMock()
    response.choices[0].message.content = content
    return response


def make_text(word_count: int) -> str:
    """Создаёт тестовый текст с заданным количеством слов."""
    return " ".join(["слово"] * word_count)


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
        self.client.chat.return_value = fake_response(make_text(36))

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 36)
        self.client.chat.assert_called_once()

    def test_accepts_maximum_allowed_word_count(self) -> None:
        self.client.chat.return_value = fake_response(make_text(44))

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 44)
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
        short_text = make_text(30)
        corrected_text = make_text(40)

        self.client.chat.side_effect = [
            fake_response(short_text),
            fake_response(corrected_text),
        ]

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(text, corrected_text)
        self.assertEqual(self.client.chat.call_count, 2)

    def test_corrects_text_that_is_too_long(self) -> None:
        long_text = make_text(50)
        corrected_text = make_text(40)

        self.client.chat.side_effect = [
            fake_response(long_text),
            fake_response(corrected_text),
        ]

        text = generate_content("Тест", "VK", "профессиональная", 40)

        self.assertEqual(text, corrected_text)
        self.assertEqual(self.client.chat.call_count, 2)

    def test_uses_multiple_correction_attempts_if_needed(self) -> None:
        responses = [
            fake_response(make_text(25)),
            fake_response(make_text(30)),
            fake_response(make_text(40)),
        ]
        self.client.chat.side_effect = responses

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(count_words(text), 40)
        self.assertEqual(
            self.client.chat.call_count,
            MAX_REVISION_ATTEMPTS + 1,
        )

    def test_returns_closest_result_after_all_attempts(self) -> None:
        first_text = make_text(30)
        second_text = make_text(32)
        best_text = make_text(34)

        self.client.chat.side_effect = [
            fake_response(first_text),
            fake_response(second_text),
            fake_response(best_text),
        ]

        text = generate_content("Тест", "Telegram", "нейтральная", 40)

        self.assertEqual(text, best_text)
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


if __name__ == "__main__":
    unittest.main()
