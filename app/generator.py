import json
import math
import re

import httpx
from gigachat import GigaChat
from gigachat.exceptions import (
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    GigaChatException,
    LengthFinishReasonError,
    ModelNotSpecifiedError,
    NotFoundError,
    RateLimitError,
    RequestEntityTooLargeError,
    ResponseError,
    ServerError,
    UnprocessableEntityError,
)
from gigachat.models import Chat, Messages, MessagesRole

from app.config import (
    GIGACHAT_CREDENTIALS,
    MAX_REVISION_ATTEMPTS,
    MAX_TOKENS,
    MODEL_NAME,
    REPETITION_PENALTY,
    TEMPERATURE,
    TOP_P,
    WORD_COUNT_TOLERANCE,
)
from app.logger import setup_logger
from app.prompts import (
    SYSTEM_PROMPT,
    VARIANT_STYLES,
    build_prompt,
    build_variant_prompt,
)


logger = setup_logger()


class ContentGenerationError(Exception):
    """Ошибка при генерации текста."""


def count_words(text: str) -> int:
    """Подсчитывает количество слов в тексте."""

    words = re.findall(
        r"[^\W\d_]+(?:[-’'][^\W\d_]+)*",
        text,
        flags=re.UNICODE,
    )

    return len(words)


def _request_gigachat(messages: list[Messages]) -> str:
    """Отправляет запрос в GigaChat и возвращает текст ответа."""

    try:
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            model=MODEL_NAME,
            verify_ssl_certs=False,
        ) as giga:
            response = giga.chat(
                Chat(
                    messages=messages,
                    temperature=TEMPERATURE,
                    top_p=TOP_P,
                    repetition_penalty=REPETITION_PENALTY,
                    max_tokens=MAX_TOKENS,
                )
            )

        if not response.choices:
            raise ContentGenerationError(
                "Модель не вернула вариантов ответа. "
                "Попробуйте повторить запрос."
            )

        result = response.choices[0].message.content

        if not result or not result.strip():
            raise ContentGenerationError(
                "Модель вернула пустой текст. "
                "Попробуйте изменить запрос."
            )

        return result.strip()

    except AuthenticationError as error:
        logger.exception("Ошибка аутентификации GigaChat")
        raise ContentGenerationError(
            "Не удалось авторизоваться в GigaChat. "
            "Проверьте настройки API."
        ) from error

    except ForbiddenError as error:
        logger.exception("Доступ к GigaChat запрещён")
        raise ContentGenerationError(
            "Доступ к модели запрещён. Проверьте права доступа "
            "и настройки API."
        ) from error

    except RateLimitError as error:
        logger.exception("Превышен лимит запросов GigaChat")

        headers = getattr(error, "headers", None)
        retry_after = headers.get("retry-after") if headers else None

        if retry_after:
            try:
                retry_seconds = int(retry_after)
                message = (
                    f"Превышен лимит запросов к GigaChat. "
                    f"Попробуйте повторить запрос через "
                    f"{retry_seconds} сек."
                )
            except (TypeError, ValueError):
                message = (
                    "Превышен лимит запросов к GigaChat. "
                    "Попробуйте повторить запрос позже."
                )
        else:
            message = (
                "Превышен лимит запросов к GigaChat. "
                "Попробуйте повторить запрос позже."
            )

        raise ContentGenerationError(message) from error

    except BadRequestError as error:
        logger.exception("Некорректный запрос к GigaChat")
        raise ContentGenerationError(
            "GigaChat отклонил запрос. Проверьте входные данные."
        ) from error

    except NotFoundError as error:
        logger.exception("Модель GigaChat не найдена")
        raise ContentGenerationError(
            "Указанная модель GigaChat не найдена. "
            "Проверьте настройки модели."
        ) from error

    except RequestEntityTooLargeError as error:
        logger.exception("Слишком большой запрос к GigaChat")
        raise ContentGenerationError(
            "Размер запроса превышает допустимый лимит."
        ) from error

    except UnprocessableEntityError as error:
        logger.exception("GigaChat не смог обработать запрос")
        raise ContentGenerationError(
            "Модель не смогла обработать запрос. "
            "Попробуйте изменить формулировку."
        ) from error

    except ServerError as error:
        logger.exception("Ошибка сервера GigaChat")
        raise ContentGenerationError(
            "На стороне GigaChat произошла ошибка сервера. "
            "Попробуйте повторить запрос позже."
        ) from error

    except LengthFinishReasonError as error:
        logger.exception("Ответ GigaChat превысил допустимую длину")
        raise ContentGenerationError(
            "Ответ оказался слишком длинным. "
            "Попробуйте уменьшить желаемый объём текста."
        ) from error

    except ModelNotSpecifiedError as error:
        logger.exception("Не указана модель GigaChat")
        raise ContentGenerationError(
            "Не удалось определить модель GigaChat."
        ) from error

    except ResponseError as error:
        logger.exception("Ошибка ответа GigaChat")
        raise ContentGenerationError(
            "Не удалось получить корректный ответ от GigaChat."
        ) from error

    except GigaChatException as error:
        logger.exception("Неизвестная ошибка GigaChat")
        raise ContentGenerationError(
            "Произошла ошибка при обращении к GigaChat."
        ) from error

    except httpx.TimeoutException as error:
        logger.exception("Истекло время ожидания ответа GigaChat")
        raise ContentGenerationError(
            "Превышено время ожидания ответа GigaChat. "
            "Попробуйте повторить запрос."
        ) from error

    except httpx.TransportError as error:
        logger.exception("Ошибка сетевого подключения к GigaChat")
        raise ContentGenerationError(
            "Не удалось подключиться к GigaChat. "
            "Проверьте интернет-соединение."
        ) from error


def _get_word_count_limits(target_word_count: int) -> tuple[int, int]:
    """Возвращает допустимые нижнюю и верхнюю границы объёма."""

    minimum_words = math.ceil(
        target_word_count * (1 - WORD_COUNT_TOLERANCE)
    )
    maximum_words = math.floor(
        target_word_count * (1 + WORD_COUNT_TOLERANCE)
    )

    return minimum_words, maximum_words


def _build_revision_prompt(
    original_text: str,
    target_word_count: int,
    actual_word_count: int,
    style: str | None = None,
) -> str:
    """Формирует запрос на корректировку количества слов."""

    minimum_words, maximum_words = _get_word_count_limits(
        target_word_count
    )

    if actual_word_count < minimum_words:
        difference = target_word_count - actual_word_count
        correction_instruction = (
            f"Текст слишком короткий. Необходимо добавить примерно "
            f"{difference} слов. Расширь содержание: подробнее раскрой "
            f"уже имеющиеся мысли, добавь полезные пояснения и детали. "
            f"Не используй искусственные повторы."
        )
    else:
        difference = actual_word_count - target_word_count
        correction_instruction = (
            f"Текст слишком длинный. Необходимо убрать примерно "
            f"{difference} слов. Сократи второстепенные детали, "
            f"повторы и избыточные формулировки. Сохрани основную "
            f"мысль и важную информацию."
        )

    style_instruction = ""

    if style and style in VARIANT_STYLES:
        style_instruction = (
            f"\nСтиль публикации: {VARIANT_STYLES[style]['label']}. "
            f"{VARIANT_STYLES[style]['description']}\n"
            "Сохрани этот способ подачи материала.\n"
        )

    return f"""
Отредактируй текст, чтобы привести его к заданному количеству слов.

ТРЕБОВАНИЯ К ОБЪЁМУ:
- Желаемое количество: {target_word_count} слов.
- Допустимый диапазон: от {minimum_words} до {maximum_words} слов.
- Текущий объём: {actual_word_count} слов.

НЕОБХОДИМОЕ ДЕЙСТВИЕ:
{correction_instruction}

ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ:
- Сохрани тему, основную мысль и фактическое содержание.
- Сохрани выбранную тональность.
- Не добавляй вымышленные факты, статистику и события.
- Не заменяй содержательную информацию общими фразами.
- Не добавляй пояснения о внесённых изменениях.
{style_instruction}
Верни только готовый текст публикации.

ИСХОДНЫЙ ТЕКСТ:
{original_text}
""".strip()


def _correct_word_count(
    text: str,
    target_word_count: int,
) -> str:
    """Пытается привести текст к заданному количеству слов."""

    minimum_words, maximum_words = _get_word_count_limits(
        target_word_count
    )

    current_text = text

    for attempt in range(MAX_REVISION_ATTEMPTS + 1):
        actual_count = count_words(current_text)

        if minimum_words <= actual_count <= maximum_words:
            logger.info(
                "Количество слов соответствует требованиям: %s",
                actual_count,
            )
            return current_text

        if attempt == MAX_REVISION_ATTEMPTS:
            break

        logger.info(
            "Корректировка объёма текста: попытка %s, "
            "текущий объём=%s, целевой объём=%s",
            attempt + 1,
            actual_count,
            target_word_count,
        )

        revision_prompt = _build_revision_prompt(
            original_text=current_text,
            target_word_count=target_word_count,
            actual_word_count=actual_count,
        )

        current_text = _request_gigachat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=SYSTEM_PROMPT,
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=revision_prompt,
                ),
            ]
        )

    logger.warning(
        "Не удалось точно скорректировать количество слов: "
        "фактическое=%s, целевое=%s",
        count_words(current_text),
        target_word_count,
    )

    return current_text


def generate_content(
    topic: str,
    platform: str,
    tone: str,
    word_count: int,
) -> str:
    """Генерирует текст с помощью GigaChat."""

    if not topic or not topic.strip():
        raise ValueError("Тема не может быть пустой.")

    if not platform or not platform.strip():
        raise ValueError("Необходимо выбрать платформу.")

    if not tone or not tone.strip():
        raise ValueError("Необходимо выбрать тональность.")

    if not isinstance(word_count, int) or isinstance(word_count, bool):
        raise ValueError("Количество слов должно быть целым числом.")

    if word_count <= 0:
        raise ValueError("Количество слов должно быть положительным.")

    logger.info(
        "Начало генерации текста: platform=%s, tone=%s, "
        "word_count=%s",
        platform,
        tone,
        word_count,
    )

    prompt = build_prompt(
        topic=topic.strip(),
        platform=platform,
        tone=tone,
        word_count=word_count,
    )

    result = _request_gigachat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=SYSTEM_PROMPT,
            ),
            Messages(
                role=MessagesRole.USER,
                content=prompt,
            ),
        ]
    )

    result = _correct_word_count(
        text=result,
        target_word_count=word_count,
    )

    logger.info(
        "Генерация завершена: actual_word_count=%s",
        count_words(result),
    )

    return result


def _parse_variants_response(
    response: str,
    expected_styles: list[str],
) -> dict[str, str]:
    """Разбирает JSON с вариантами текста, полученный от модели."""

    cleaned_response = response.strip()

    if cleaned_response.startswith("```"):
        cleaned_response = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned_response,
            flags=re.IGNORECASE,
        )
        cleaned_response = re.sub(
            r"\s*```$",
            "",
            cleaned_response,
        )

    try:
        data = json.loads(cleaned_response)

    except json.JSONDecodeError as error:
        logger.exception("Не удалось разобрать JSON с вариантами")
        raise ContentGenerationError(
            "Модель вернула данные в неправильном формате."
        ) from error

    if not isinstance(data, dict):
        raise ContentGenerationError(
            "Некорректная структура ответа модели."
        )

    variants = data.get("variants")

    if not isinstance(variants, list):
        raise ContentGenerationError(
            "В ответе модели отсутствует список вариантов."
        )

    if len(variants) != len(expected_styles):
        raise ContentGenerationError(
            "Модель вернула неправильное количество вариантов."
        )

    parsed_variants = {}

    for variant in variants:
        if not isinstance(variant, dict):
            raise ContentGenerationError(
                "Один из вариантов имеет некорректный формат."
            )

        style = variant.get("style")
        text = variant.get("text")

        if style not in expected_styles:
            raise ContentGenerationError(
                "Модель вернула неизвестный стиль варианта."
            )

        if style in parsed_variants:
            raise ContentGenerationError(
                "Модель вернула несколько вариантов одного стиля."
            )

        if not isinstance(text, str) or not text.strip():
            raise ContentGenerationError(
                "Один из вариантов содержит текст, который должен быть "
                "не пустым."
            )

        parsed_variants[style] = text.strip()

    if set(parsed_variants) != set(expected_styles):
        raise ContentGenerationError(
            "Модель вернула не все запрошенные стили."
        )

    return parsed_variants


def _correct_variant_word_count(
    text: str,
    target_word_count: int,
    style: str,
) -> dict:
    """
    Корректирует объём варианта и возвращает результат проверки.

    Если после всех попыток текст не попал в допустимый диапазон,
    возвращает последний результат со статусом is_valid=False.
    """

    minimum_words, maximum_words = _get_word_count_limits(
        target_word_count
    )

    current_text = text

    for attempt in range(MAX_REVISION_ATTEMPTS + 1):
        actual_count = count_words(current_text)

        if minimum_words <= actual_count <= maximum_words:
            logger.info(
                "Объём варианта '%s' соответствует требованиям: %s слов",
                style,
                actual_count,
            )

            return {
                "text": current_text,
                "word_count": actual_count,
                "is_valid": True,
                "min_word_count": minimum_words,
                "max_word_count": maximum_words,
            }

        if attempt == MAX_REVISION_ATTEMPTS:
            break

        logger.info(
            "Корректировка варианта '%s': попытка %s, "
            "текущий объём=%s, целевой объём=%s",
            style,
            attempt + 1,
            actual_count,
            target_word_count,
        )

        revision_prompt = _build_revision_prompt(
            original_text=current_text,
            target_word_count=target_word_count,
            actual_word_count=actual_count,
            style=style,
        )

        current_text = _request_gigachat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=SYSTEM_PROMPT,
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=revision_prompt,
                ),
            ]
        )

    actual_count = count_words(current_text)

    logger.warning(
        "Вариант '%s' не достиг допустимого объёма: "
        "фактическое=%s, допустимый диапазон=%s-%s",
        style,
        actual_count,
        minimum_words,
        maximum_words,
    )

    return {
        "text": current_text,
        "word_count": actual_count,
        "is_valid": False,
        "min_word_count": minimum_words,
        "max_word_count": maximum_words,
    }


def generate_variants(
    topic: str,
    platform: str,
    tone: str,
    word_count: int,
    variant_count: int = 4,
) -> list[dict]:
    """Генерирует несколько вариантов текста с разной подачей."""

    if not topic or not topic.strip():
        raise ValueError("Тема не может быть пустой.")

    if not platform or not platform.strip():
        raise ValueError("Необходимо выбрать платформу.")

    if not tone or not tone.strip():
        raise ValueError("Необходимо выбрать тональность.")

    if not isinstance(word_count, int) or isinstance(word_count, bool):
        raise ValueError("Количество слов должно быть целым числом.")

    if word_count <= 0:
        raise ValueError("Количество слов должно быть положительным.")

    if (
        not isinstance(variant_count, int)
        or isinstance(variant_count, bool)
        or variant_count < 1
        or variant_count > len(VARIANT_STYLES)
    ):
        raise ValueError(
            f"Количество вариантов должно быть от 1 до "
            f"{len(VARIANT_STYLES)}."
        )

    selected_styles = list(VARIANT_STYLES.keys())[:variant_count]

    logger.info(
        "Начало генерации вариантов: platform=%s, tone=%s, "
        "word_count=%s, variant_count=%s",
        platform,
        tone,
        word_count,
        variant_count,
    )

    result = []

    for style in selected_styles:
        style_info = VARIANT_STYLES[style]

        logger.info(
            "Генерация варианта: style=%s, label=%s",
            style,
            style_info["label"],
        )

        prompt = build_variant_prompt(
            topic=topic.strip(),
            platform=platform,
            tone=tone,
            word_count=word_count,
            style=style,
        )

        generated_text = _request_gigachat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=SYSTEM_PROMPT,
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=prompt,
                ),
            ]
        )

        correction_result = _correct_variant_word_count(
            text=generated_text,
            target_word_count=word_count,
            style=style,
        )

        result.append(
            {
                "style": style,
                "label": style_info["label"],
                "description": style_info["description"],
                "text": correction_result["text"],
                "word_count": correction_result["word_count"],
                "is_valid": correction_result["is_valid"],
                "min_word_count": correction_result["min_word_count"],
                "max_word_count": correction_result["max_word_count"],
            }
        )

    logger.info(
        "Генерация вариантов завершена: количество=%s",
        len(result),
    )

    return result