
import unittest
from unittest.mock import MagicMock, patch

import httpx
from gigachat.exceptions import (
    AuthenticationError,
    RateLimitError,
    ServerError,
)

from app.generator import ContentGenerationError, generate_content


def fake_response(content: str) -> MagicMock:
    """Создаёт имитацию ответа GigaChat с указанным текстом."""
    response = MagicMock()
    response.choices[0].message.content = content
    return response


class GenerateContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_patch = patch("app.generator.GigaChat")
        self.giga_class = self.client_patch.start()
        self.client = self.giga_class.return_value.__enter__.return_value
        self.addCleanup(self.client_patch.stop)

    def test_returns_generated_text(self) -> None:
        self.client.chat.return_value = fake_response("Готовый пост о теме")

        text = generate_content(
            "ИИ в образовании",
            "Telegram",
            "дружелюбная",
            40,
        )

        self.assertEqual(text, "Готовый пост о теме")
        self.client.chat.assert_called_once()

    def test_raises_for_empty_text(self) -> None:
        self.client.chat.return_value = fake_response("")

        with self.assertRaisesRegex(ContentGenerationError, "пустой текст"):
            generate_content("ИИ в образовании", "Telegram", "дружелюбная", 40)

    def test_raises_for_whitespace_only_text(self) -> None:
        self.client.chat.return_value = fake_response(" \n\t ")

        with self.assertRaises(ContentGenerationError):
            generate_content("ИИ в образовании", "VK", "нейтральная", 40)

    def test_handles_authentication_error(self) -> None:
        self.client.chat.side_effect = AuthenticationError(
            "https://gigachat.example",
            401,
            b"Unauthorized",
            None,
        )

        with self.assertRaisesRegex(ContentGenerationError, "авторизоваться"):
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
        self.client.chat.side_effect = httpx.TimeoutException("Connection timed out")

        with self.assertRaisesRegex(ContentGenerationError, "время ожидания"):
            generate_content("Тест", "Telegram", "нейтральная", 40)


if __name__ == "__main__":
    unittest.main()
