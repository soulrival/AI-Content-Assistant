
import unittest
from unittest.mock import patch

from app.editor import edit_content
from app.generator import ContentGenerationError
from app.prompts import build_edit_prompt


class EditContentTests(unittest.TestCase):

    @patch("app.editor._request_gigachat")
    def test_returns_edited_text(self, mock_request):
        mock_request.return_value = "Улучшенный текст публикации."

        result = edit_content(
            text="Исходный текст.",
            action="improve",
        )

        self.assertEqual(result, "Улучшенный текст публикации.")
        mock_request.assert_called_once()

    def test_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            edit_content("", "improve")

    def test_rejects_whitespace_text(self):
        with self.assertRaises(ValueError):
            edit_content("   ", "improve")

    def test_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            edit_content("Текст.", "unknown")

    def test_custom_action_requires_instruction(self):
        with self.assertRaises(ValueError):
            edit_content("Текст.", "custom")

    def test_tone_action_requires_valid_tone(self):
        with self.assertRaises(ValueError):
            edit_content(
                text="Текст.",
                action="change_tone",
                tone="неизвестная",
            )

    @patch("app.editor._request_gigachat")
    def test_passes_selected_tone(self, mock_request):
        mock_request.return_value = "Профессиональный текст."

        edit_content(
            text="Исходный текст.",
            action="change_tone",
            tone="профессиональная",
        )

        messages = mock_request.call_args.kwargs["messages"]
        self.assertIn("профессиональная", messages[1].content)

    @patch("app.editor._request_gigachat")
    def test_passes_custom_instruction(self, mock_request):
        mock_request.return_value = "Отредактированный текст."

        edit_content(
            text="Исходный текст.",
            action="improve",
            custom_instruction="Сделай вступление короче.",
        )

        messages = mock_request.call_args.kwargs["messages"]
        self.assertIn("Сделай вступление короче.", messages[1].content)

    @patch("app.editor._request_gigachat")
    def test_propagates_api_error(self, mock_request):
        mock_request.side_effect = ContentGenerationError(
            "Ошибка GigaChat."
        )

        with self.assertRaises(ContentGenerationError):
            edit_content("Исходный текст.", "improve")


class BuildEditPromptTests(unittest.TestCase):

    def test_prompt_contains_source_text(self):
        prompt = build_edit_prompt(
            text="Текст для редактирования.",
            action="improve",
        )

        self.assertIn("Текст для редактирования.", prompt)

    def test_prompt_contains_action_instruction(self):
        prompt = build_edit_prompt(
            text="Исходный текст.",
            action="shorten",
        )

        self.assertIn("Сократи текст", prompt)

    def test_prompt_contains_custom_instruction(self):
        prompt = build_edit_prompt(
            text="Исходный текст.",
            action="improve",
            custom_instruction="Добавь более интересное вступление.",
        )

        self.assertIn(
            "Добавь более интересное вступление.",
            prompt,
        )

    def test_prompt_contains_selected_tone(self):
        prompt = build_edit_prompt(
            text="Исходный текст.",
            action="change_tone",
            tone="дружелюбная",
        )

        self.assertIn("дружелюбная", prompt)

    def test_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            build_edit_prompt(
                text="Исходный текст.",
                action="unknown",
            )


if __name__ == "__main__":
    unittest.main()
