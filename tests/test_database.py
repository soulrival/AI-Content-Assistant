import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database import (
    delete_generation,
    get_generation,
    get_generations,
    init_db,
    save_generation,
    save_generations,
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

    def _sample_variants(self):
        return [
            {
                "style": "informational",
                "label": "Информационный",
                "description": "Факты и объяснения.",
                "text": "Информационный текст публикации.",
                "word_count": 40,
                "is_valid": True,
                "min_word_count": 32,
                "max_word_count": 48,
            },
            {
                "style": "engaging",
                "label": "Вовлекающий",
                "description": "Яркое начало и вопрос.",
                "text": "Вовлекающий текст публикации.",
                "word_count": 55,
                "is_valid": False,
                "min_word_count": 32,
                "max_word_count": 48,
            },
        ]

    def _save_sample_variants(self, **settings):
        return save_generations(
            topic="Искусственный интеллект",
            platform="Telegram",
            tone="дружелюбная",
            target_word_count=40,
            variants=self._sample_variants(),
            db_path=self.db_path,
            **settings,
        )

    def test_init_db_creates_database(self):
        self.assertTrue(self.db_path.exists())

        generations = get_generations(db_path=self.db_path)
        self.assertEqual(generations, [])

    def test_init_db_creates_required_columns(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(generations)"
                ).fetchall()
            }

        expected_columns = {
            "id",
            "topic",
            "generated_text",
            "platform",
            "tone",
            "target_word_count",
            "actual_word_count",
            "created_at",
            "variant_group_id",
            "style",
            "style_label",
            "style_description",
            "is_valid",
            "min_word_count",
            "max_word_count",
            "target_audience",
            "publication_goal",
            "additional_wishes",
        }

        self.assertTrue(expected_columns.issubset(columns))

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

    def test_save_generations_returns_ids(self):
        generation_ids = self._save_sample_variants()

        self.assertEqual(len(generation_ids), 2)
        self.assertTrue(
            all(isinstance(item, int) for item in generation_ids)
        )
        self.assertTrue(all(item > 0 for item in generation_ids))

    def test_save_generations_saves_all_variants(self):
        generation_ids = self._save_sample_variants()
        generations = get_generations(db_path=self.db_path)

        self.assertEqual(len(generations), 2)
        self.assertEqual(
            {item["id"] for item in generations},
            set(generation_ids),
        )

    def test_saved_variants_have_same_group_id(self):
        self._save_sample_variants()

        generations = get_generations(db_path=self.db_path)
        group_ids = {
            item["variant_group_id"]
            for item in generations
        }

        self.assertEqual(len(group_ids), 1)
        self.assertIsNotNone(next(iter(group_ids)))

    def test_saved_variants_have_different_styles(self):
        self._save_sample_variants()

        generations = get_generations(db_path=self.db_path)

        self.assertEqual(
            {item["style"] for item in generations},
            {"informational", "engaging"},
        )

    def test_saved_variants_keep_metadata(self):
        self._save_sample_variants()

        generations = get_generations(db_path=self.db_path)
        informational = next(
            item
            for item in generations
            if item["style"] == "informational"
        )

        self.assertEqual(
            informational["style_label"],
            "Информационный",
        )
        self.assertEqual(
            informational["style_description"],
            "Факты и объяснения.",
        )
        self.assertEqual(
            informational["generated_text"],
            "Информационный текст публикации.",
        )
        self.assertEqual(informational["actual_word_count"], 40)

    def test_saves_validation_status_and_limits(self):
        self._save_sample_variants()

        generations = get_generations(db_path=self.db_path)

        informational = next(
            item
            for item in generations
            if item["style"] == "informational"
        )
        engaging = next(
            item
            for item in generations
            if item["style"] == "engaging"
        )

        self.assertEqual(informational["is_valid"], 1)
        self.assertEqual(informational["min_word_count"], 32)
        self.assertEqual(informational["max_word_count"], 48)

        self.assertEqual(engaging["is_valid"], 0)
        self.assertEqual(engaging["min_word_count"], 32)
        self.assertEqual(engaging["max_word_count"], 48)

    def test_saves_new_generation_settings(self):
        self._save_sample_variants(
            target_audience="Специалисты",
            publication_goal="Вовлекать",
            additional_wishes="Добавь практический пример.",
        )

        generations = get_generations(db_path=self.db_path)

        for generation in generations:
            with self.subTest(generation_id=generation["id"]):
                self.assertEqual(
                    generation["target_audience"],
                    "Специалисты",
                )
                self.assertEqual(
                    generation["publication_goal"],
                    "Вовлекать",
                )
                self.assertEqual(
                    generation["additional_wishes"],
                    "Добавь практический пример.",
                )

    def test_saves_empty_additional_wishes(self):
        self._save_sample_variants(
            target_audience="Начинающие",
            publication_goal="Информировать",
            additional_wishes="",
        )

        generations = get_generations(db_path=self.db_path)

        self.assertTrue(
            all(
                generation["additional_wishes"] == ""
                for generation in generations
            )
        )

    def test_old_save_generation_call_keeps_new_fields_null(self):
        generation_id = self._save_sample_generation()

        generation = get_generation(
            generation_id,
            db_path=self.db_path,
        )

        self.assertIsNone(generation["target_audience"])
        self.assertIsNone(generation["publication_goal"])
        self.assertIsNone(generation["additional_wishes"])

    def test_old_save_generations_call_keeps_new_fields_null(self):
        self._save_sample_variants()

        generations = get_generations(db_path=self.db_path)

        for generation in generations:
            with self.subTest(generation_id=generation["id"]):
                self.assertIsNone(generation["target_audience"])
                self.assertIsNone(generation["publication_goal"])
                self.assertIsNone(generation["additional_wishes"])

    def test_save_generations_rejects_empty_list(self):
        with self.assertRaises(ValueError):
            save_generations(
                topic="Тема",
                platform="Telegram",
                tone="нейтральная",
                target_word_count=40,
                variants=[],
                db_path=self.db_path,
            )

    def test_save_generations_rejects_missing_fields(self):
        invalid_variant = {
            "style": "informational",
            "label": "Информационный",
        }

        with self.assertRaises(ValueError):
            save_generations(
                topic="Тема",
                platform="Telegram",
                tone="нейтральная",
                target_word_count=40,
                variants=[invalid_variant],
                db_path=self.db_path,
            )

        self.assertEqual(
            get_generations(db_path=self.db_path),
            [],
        )

    def test_save_generations_rejects_empty_text(self):
        variants = self._sample_variants()
        variants[0]["text"] = "   "

        with self.assertRaises(ValueError):
            save_generations(
                topic="Тема",
                platform="Telegram",
                tone="нейтральная",
                target_word_count=40,
                variants=variants,
                db_path=self.db_path,
            )

        self.assertEqual(
            get_generations(db_path=self.db_path),
            [],
        )

    def test_save_generations_rejects_invalid_word_count(self):
        variants = self._sample_variants()
        variants[0]["word_count"] = -1

        with self.assertRaises(ValueError):
            save_generations(
                topic="Тема",
                platform="Telegram",
                tone="нейтральная",
                target_word_count=40,
                variants=variants,
                db_path=self.db_path,
            )

        self.assertEqual(
            get_generations(db_path=self.db_path),
            [],
        )

    def test_save_generations_rejects_invalid_status_type(self):
        variants = self._sample_variants()
        variants[0]["is_valid"] = "да"

        with self.assertRaises(ValueError):
            save_generations(
                topic="Тема",
                platform="Telegram",
                tone="нейтральная",
                target_word_count=40,
                variants=variants,
                db_path=self.db_path,
            )

    def test_save_generations_rejects_invalid_limits(self):
        variants = self._sample_variants()
        variants[0]["min_word_count"] = 50
        variants[0]["max_word_count"] = 40

        with self.assertRaises(ValueError):
            save_generations(
                topic="Тема",
                platform="Telegram",
                tone="нейтральная",
                target_word_count=40,
                variants=variants,
                db_path=self.db_path,
            )

    def test_init_db_migrates_existing_database(self):
        old_db_path = Path(self.temp_dir.name) / "old_history.db"

        with closing(sqlite3.connect(old_db_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE generations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic TEXT NOT NULL,
                        generated_text TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        tone TEXT NOT NULL,
                        target_word_count INTEGER NOT NULL,
                        actual_word_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO generations (
                        topic,
                        generated_text,
                        platform,
                        tone,
                        target_word_count,
                        actual_word_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Старая тема",
                        "Старый текст",
                        "Telegram",
                        "нейтральная",
                        100,
                        95,
                    ),
                )

        init_db(old_db_path)

        generation = get_generation(1, db_path=old_db_path)

        self.assertIsNotNone(generation)
        self.assertEqual(generation["topic"], "Старая тема")
        self.assertEqual(generation["generated_text"], "Старый текст")

        self.assertIsNone(generation["is_valid"])
        self.assertIsNone(generation["min_word_count"])
        self.assertIsNone(generation["max_word_count"])

        self.assertIsNone(generation["target_audience"])
        self.assertIsNone(generation["publication_goal"])
        self.assertIsNone(generation["additional_wishes"])

    def test_migration_preserves_existing_records(self):
        old_db_path = Path(self.temp_dir.name) / "preserve_history.db"

        with closing(sqlite3.connect(old_db_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE generations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic TEXT NOT NULL,
                        generated_text TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        tone TEXT NOT NULL,
                        target_word_count INTEGER NOT NULL,
                        actual_word_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                connection.executemany(
                    """
                    INSERT INTO generations (
                        topic,
                        generated_text,
                        platform,
                        tone,
                        target_word_count,
                        actual_word_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "Первая тема",
                            "Первый текст",
                            "Telegram",
                            "нейтральная",
                            100,
                            95,
                        ),
                        (
                            "Вторая тема",
                            "Второй текст",
                            "VK",
                            "дружелюбная",
                            150,
                            145,
                        ),
                    ],
                )

        init_db(old_db_path)

        generations = get_generations(db_path=old_db_path)

        self.assertEqual(len(generations), 2)
        self.assertEqual(
            {item["topic"] for item in generations},
            {"Первая тема", "Вторая тема"},
        )


if __name__ == "__main__":
    unittest.main()