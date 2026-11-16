import unittest
from unittest.mock import MagicMock, patch

from app.generator import generate_content


def fake_response(content: str) -> MagicMock:
    """Ответ клиента с нужным текстом в choices[0].message.content."""
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

        text = generate_content("ИИ в образовании", "Telegram", "дружелюбная", 40)

        self.assertEqual(text, "Готовый пост о теме")
        self.client.chat.assert_called_once()

    def test_raises_for_empty_text(self) -> None:
        self.client.chat.return_value = fake_response("")

        with self.assertRaises(ValueError):
            generate_content("ИИ в образовании", "Telegram", "дружелюбная", 40)

    def test_raises_for_whitespace_only_text(self) -> None:
        self.client.chat.return_value = fake_response(" \n\t ")

        with self.assertRaises(ValueError):
            generate_content("ИИ в образовании", "VK", "нейтральная", 40)


if __name__ == "__main__":
    unittest.main()
