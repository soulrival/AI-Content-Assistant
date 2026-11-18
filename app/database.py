
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4


# Путь к базе данных относительно корня проекта.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"


@contextmanager
def _connect(
    db_path: str | Path = DB_PATH,
) -> Iterator[sqlite3.Connection]:
    """Создаёт подключение и гарантированно закрывает его."""

    database_path = Path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    """Добавляет столбец, если его ещё нет в таблице."""

    existing_columns = {
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db(db_path: str | Path = DB_PATH) -> None:
    """Создаёт таблицы истории и обновляет их структуру при необходимости."""

    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS generations (
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

        # Дополнительные поля для группировки вариантов.
        _add_column_if_missing(
            connection,
            "generations",
            "variant_group_id",
            "TEXT",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "style",
            "TEXT",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "style_label",
            "TEXT",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "style_description",
            "TEXT",
        )

        # Результат проверки количества слов.
        _add_column_if_missing(
            connection,
            "generations",
            "is_valid",
            "INTEGER",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "min_word_count",
            "INTEGER",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "max_word_count",
            "INTEGER",
        )

        # Дополнительные настройки генерации.
        _add_column_if_missing(
            connection,
            "generations",
            "target_audience",
            "TEXT",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "publication_goal",
            "TEXT",
        )
        _add_column_if_missing(
            connection,
            "generations",
            "additional_wishes",
            "TEXT",
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                edited_text TEXT NOT NULL,
                action TEXT NOT NULL,
                action_label TEXT NOT NULL,
                tone TEXT,
                custom_instruction TEXT,
                source_generation_id INTEGER,
                actual_word_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_generation(
    topic: str,
    generated_text: str,
    platform: str,
    tone: str,
    target_word_count: int,
    actual_word_count: int,
    db_path: str | Path = DB_PATH,
    target_audience: str | None = None,
    publication_goal: str | None = None,
    additional_wishes: str | None = None,
) -> int:
    """Сохраняет одиночную генерацию и возвращает её идентификатор."""

    if target_audience is not None and (
        not isinstance(target_audience, str) or not target_audience.strip()
    ):
        raise ValueError("Целевая аудитория должна быть указана текстом.")

    if publication_goal is not None and (
        not isinstance(publication_goal, str) or not publication_goal.strip()
    ):
        raise ValueError("Цель публикации должна быть указана текстом.")

    if additional_wishes is not None and not isinstance(additional_wishes, str):
        raise ValueError("Дополнительные пожелания должны быть текстом.")

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO generations (
                topic,
                generated_text,
                platform,
                tone,
                target_word_count,
                actual_word_count,
                target_audience,
                publication_goal,
                additional_wishes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic,
                generated_text,
                platform,
                tone,
                target_word_count,
                actual_word_count,
                target_audience,
                publication_goal,
                additional_wishes.strip() if additional_wishes is not None else None,
            ),
        )

        return int(cursor.lastrowid)


def save_generations(
    topic: str,
    platform: str,
    tone: str,
    target_word_count: int,
    variants: list[dict],
    db_path: str | Path = DB_PATH,
    target_audience: str | None = None,
    publication_goal: str | None = None,
    additional_wishes: str | None = None,
) -> list[int]:
    """
    Сохраняет несколько вариантов одной генерации.

    Все варианты получают общий variant_group_id.
    Возвращает список идентификаторов сохранённых записей.
    """

    if not variants:
        raise ValueError("Список вариантов не может быть пустым.")

    if target_audience is not None and (
        not isinstance(target_audience, str) or not target_audience.strip()
    ):
        raise ValueError("Целевая аудитория должна быть указана текстом.")

    if publication_goal is not None and (
        not isinstance(publication_goal, str) or not publication_goal.strip()
    ):
        raise ValueError("Цель публикации должна быть указана текстом.")

    if additional_wishes is not None and not isinstance(additional_wishes, str):
        raise ValueError("Дополнительные пожелания должны быть текстом.")

    required_fields = {
        "style",
        "label",
        "description",
        "text",
        "word_count",
    }

    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            raise ValueError(
                f"Вариант №{index} должен быть словарём."
            )

        missing_fields = required_fields - variant.keys()

        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(
                f"В варианте №{index} отсутствуют поля: {missing}."
            )

        for field in ("style", "label", "description", "text"):
            if (
                not isinstance(variant[field], str)
                or not variant[field].strip()
            ):
                raise ValueError(
                    f"Поле «{field}» в варианте №{index} "
                    "должно содержать текст."
                )

        if (
            not isinstance(variant["word_count"], int)
            or isinstance(variant["word_count"], bool)
            or variant["word_count"] < 0
        ):
            raise ValueError(
                f"Количество слов в варианте №{index} "
                "должно быть неотрицательным целым числом."
            )

        is_valid = variant.get("is_valid")

        if is_valid is not None and not isinstance(is_valid, bool):
            raise ValueError(
                f"Статус проверки в варианте №{index} "
                "должен иметь логический тип."
            )

        for field in ("min_word_count", "max_word_count"):
            value = variant.get(field)

            if value is not None and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(
                    f"Поле «{field}» в варианте №{index} "
                    "должно быть неотрицательным целым числом."
                )

        minimum = variant.get("min_word_count")
        maximum = variant.get("max_word_count")

        if (
            minimum is not None
            and maximum is not None
            and minimum > maximum
        ):
            raise ValueError(
                f"В варианте №{index} нижняя граница объёма "
                "не может превышать верхнюю."
            )

    # Общий идентификатор позволяет объединить варианты в одну серию.
    variant_group_id = str(uuid4())
    generation_ids = []

    with _connect(db_path) as connection:
        for variant in variants:
            is_valid = variant.get("is_valid")

            cursor = connection.execute(
                """
                INSERT INTO generations (
                    topic,
                    generated_text,
                    platform,
                    tone,
                    target_word_count,
                    actual_word_count,
                    variant_group_id,
                    style,
                    style_label,
                    style_description,
                    is_valid,
                    min_word_count,
                    max_word_count,
                    target_audience,
                    publication_goal,
                    additional_wishes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic,
                    variant["text"],
                    platform,
                    tone,
                    target_word_count,
                    variant["word_count"],
                    variant_group_id,
                    variant["style"],
                    variant["label"],
                    variant["description"],
                    int(is_valid) if is_valid is not None else None,
                    variant.get("min_word_count"),
                    variant.get("max_word_count"),
                    target_audience,
                    publication_goal,
                    (
                        additional_wishes.strip()
                        if additional_wishes is not None
                        else None
                    ),
                ),
            )

            generation_ids.append(int(cursor.lastrowid))

    return generation_ids


def get_generations(
    limit: int | None = None,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    """Возвращает историю генераций от новых записей к старым."""

    query = """
        SELECT *
        FROM generations
        ORDER BY id DESC
    """

    parameters = ()

    if limit is not None:
        if limit < 1:
            raise ValueError("Лимит должен быть положительным числом.")

        query += " LIMIT ?"
        parameters = (limit,)

    with _connect(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


def get_generation(
    generation_id: int,
    db_path: str | Path = DB_PATH,
) -> dict | None:
    """Возвращает одну генерацию по идентификатору."""

    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def delete_generation(
    generation_id: int,
    db_path: str | Path = DB_PATH,
) -> bool:
    """Удаляет генерацию и сообщает, была ли удалена запись."""

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        )

        return cursor.rowcount > 0


def save_edit(
    source_text: str,
    edited_text: str,
    action: str,
    action_label: str,
    actual_word_count: int,
    tone: str | None = None,
    custom_instruction: str = "",
    source_generation_id: int | None = None,
    db_path: str | Path = DB_PATH,
) -> int:
    """Сохраняет результат редактирования и возвращает его идентификатор."""

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO edits (
                source_text,
                edited_text,
                action,
                action_label,
                tone,
                custom_instruction,
                source_generation_id,
                actual_word_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_text,
                edited_text,
                action,
                action_label,
                tone,
                custom_instruction,
                source_generation_id,
                actual_word_count,
            ),
        )

        return int(cursor.lastrowid)


def get_edits(
    limit: int | None = None,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    """Возвращает историю редактирований от новых записей к старым."""

    query = """
        SELECT *
        FROM edits
        ORDER BY id DESC
    """

    parameters = ()

    if limit is not None:
        if limit < 1:
            raise ValueError("Лимит должен быть положительным числом.")

        query += " LIMIT ?"
        parameters = (limit,)

    with _connect(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


def delete_edit(
    edit_id: int,
    db_path: str | Path = DB_PATH,
) -> bool:
    """Удаляет результат редактирования."""

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM edits
            WHERE id = ?
            """,
            (edit_id,),
        )

        return cursor.rowcount > 0
