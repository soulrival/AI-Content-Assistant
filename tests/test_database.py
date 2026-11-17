
import tempfile
import unittest
from pathlib import Path

from app.database import (
    delete_generation,
    get_generation,
    get_generations,
    init_db,
    save_generation,
)


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_history.db"

        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _save_sample_generation(self, topic="Тестовая тема"):
        return save_generation(
            topic=topic,
            generated_text="Тестовый текст публикации.",
            platform="Telegram",
            tone="дружелюбная",
            target_word_count=120,
            actual_word_count=118,
            db_path=self.db_path,
        )

    def test_init_db_creates_database(self):
        self.assertTrue(self.db_path.exists())

        generations = get_generations(db_path=self.db_path)
        self.assertEqual(generations, [])

    def test_save_generation_returns_id(self):
        generation_id = self._save_sample_generation()

        self.assertIsInstance(generation_id, int)
        self.assertGreater(generation_id, 0)

    def test_get_generation_returns_saved_record(self):
        generation_id = self._save_sample_generation()

        generation = get_generation(
            generation_id,
            db_path=self.db_path,
        )

        self.assertIsNotNone(generation)
        self.assertEqual(generation["topic"], "Тестовая тема")
        self.assertEqual(
            generation["generated_text"],
            "Тестовый текст публикации.",
        )
        self.assertEqual(generation["platform"], "Telegram")
        self.assertEqual(generation["tone"], "дружелюбная")
        self.assertEqual(generation["target_word_count"], 120)
        self.assertEqual(generation["actual_word_count"], 118)

    def test_get_generation_returns_none_for_missing_id(self):
        generation = get_generation(
            999,
            db_path=self.db_path,
        )

        self.assertIsNone(generation)

    def test_get_generations_returns_newest_first(self):
        first_id = self._save_sample_generation("Первая тема")
        second_id = self._save_sample_generation("Вторая тема")

        generations = get_generations(db_path=self.db_path)

        self.assertEqual(len(generations), 2)
        self.assertEqual(generations[0]["id"], second_id)
        self.assertEqual(generations[1]["id"], first_id)

    def test_get_generations_respects_limit(self):
        self._save_sample_generation("Первая тема")
        self._save_sample_generation("Вторая тема")
        self._save_sample_generation("Третья тема")

        generations = get_generations(
            limit=2,
            db_path=self.db_path,
        )

        self.assertEqual(len(generations), 2)
        self.assertEqual(generations[0]["topic"], "Третья тема")

    def test_get_generations_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            get_generations(
                limit=0,
                db_path=self.db_path,
            )

    def test_delete_generation_removes_record(self):
        generation_id = self._save_sample_generation()

        result = delete_generation(
            generation_id,
            db_path=self.db_path,
        )

        self.assertTrue(result)
        self.assertIsNone(
            get_generation(generation_id, db_path=self.db_path)
        )

    def test_delete_generation_returns_false_for_missing_id(self):
        result = delete_generation(
            999,
            db_path=self.db_path,
        )

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
