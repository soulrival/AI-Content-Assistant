
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


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


def init_db(db_path: str | Path = DB_PATH) -> None:
    """Создаёт таблицу истории, если она ещё не существует."""

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


def save_generation(
    topic: str,
    generated_text: str,
    platform: str,
    tone: str,
    target_word_count: int,
    actual_word_count: int,
    db_path: str | Path = DB_PATH,
) -> int:
    """Сохраняет успешную генерацию и возвращает её идентификатор."""

    with _connect(db_path) as connection:
        cursor = connection.execute(
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
                topic,
                generated_text,
                platform,
                tone,
                target_word_count,
                actual_word_count,
            ),
        )

        return int(cursor.lastrowid)


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
