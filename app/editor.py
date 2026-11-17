
from gigachat.models import Messages

from app.generator import ContentGenerationError, _request_gigachat
from app.logger import setup_logger
from app.prompts import EDITOR_SYSTEM_PROMPT, build_edit_prompt


logger = setup_logger()

EDIT_ACTIONS = {
    "improve": "Улучшить текст",
    "proofread": "Исправить ошибки",
    "shorten": "Сократить",
    "expand": "Расширить",
    "change_tone": "Изменить тональность",
    "custom": "Своя инструкция",
}

AVAILABLE_TONES = [
    "нейтральная",
    "дружелюбная",
    "профессиональная",
]


def edit_content(
    text: str,
    action: str,
    custom_instruction: str = "",
    tone: str | None = None,
) -> str:
    """Редактирует готовый текст с помощью GigaChat."""

    if not text or not text.strip():
        raise ValueError("Исходный текст не может быть пустым.")

    if action not in EDIT_ACTIONS:
        raise ValueError("Выбран неизвестный режим редактирования.")

    if action == "custom" and not custom_instruction.strip():
        raise ValueError(
            "Для пользовательского режима необходимо указать инструкцию."
        )

    if action == "change_tone" and tone not in AVAILABLE_TONES:
        raise ValueError("Выберите допустимую тональность.")

    logger.info(
        "Начало редактирования: action=%s, characters=%s",
        action,
        len(text),
    )

    prompt = build_edit_prompt(
        text=text,
        action=action,
        custom_instruction=custom_instruction.strip(),
        tone=tone,
    )

    try:
        result = _request_gigachat(
            messages=[
                Messages(
                    role="system",
                    content=EDITOR_SYSTEM_PROMPT,
                ),
                Messages(
                    role="user",
                    content=prompt,
                ),
            ]
        )
    except ContentGenerationError:
        logger.exception("Не удалось отредактировать текст")
        raise

    logger.info(
        "Редактирование завершено: characters=%s",
        len(result),
    )

    return result
