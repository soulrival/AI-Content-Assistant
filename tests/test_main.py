import unittest
from unittest.mock import patch

from main import ask_choice, ask_non_empty, ask_word_count

OPTIONS = ("Telegram", "VK")


class AskNonEmptyTests(unittest.TestCase):
    @patch("builtins.input", side_effect=["", "ИИ в образовании"])
    def test_rejects_empty_input_then_accepts_topic(self, mocked_input) -> None:
        topic = ask_non_empty("Тема публикации: ")

        self.assertEqual(topic, "ИИ в образовании")
        self.assertEqual(mocked_input.call_count, 2)


class AskChoiceTests(unittest.TestCase):
    @patch("builtins.input", return_value="1")
    def test_valid_number_returns_matching_option(self, _mocked_input) -> None:
        self.assertEqual(ask_choice("Платформа:", OPTIONS), "Telegram")

    @patch("builtins.input", side_effect=["9", "2"])
    def test_rejects_invalid_number_then_accepts_valid_one(self, mocked_input) -> None:
        choice = ask_choice("Платформа:", OPTIONS)

        self.assertEqual(choice, "VK")
        self.assertEqual(mocked_input.call_count, 2)


class AskWordCountTests(unittest.TestCase):
    @patch("builtins.input", side_effect=["abc", "50"])
    def test_rejects_non_numeric_text(self, mocked_input) -> None:
        word_count = ask_word_count()

        self.assertEqual(word_count, 50)
        self.assertEqual(mocked_input.call_count, 2)

    @patch("builtins.input", side_effect=["9", "1001", "50"])
    def test_rejects_values_outside_allowed_range(self, mocked_input) -> None:
        word_count = ask_word_count()

        self.assertEqual(word_count, 50)
        self.assertEqual(mocked_input.call_count, 3)

    @patch("builtins.input", return_value="10")
    def test_accepts_minimum_word_count(self, _mocked_input) -> None:
        self.assertEqual(ask_word_count(), 10)

    @patch("builtins.input", return_value="1000")
    def test_accepts_maximum_word_count(self, _mocked_input) -> None:
        self.assertEqual(ask_word_count(), 1000)


if __name__ == "__main__":
    unittest.main()
