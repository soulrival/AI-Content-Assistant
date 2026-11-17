
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
    MODEL_NAME,
    TEMPERATURE,
    TOP_P,
    REPETITION_PENALTY,
    MAX_TOKENS,
    WORD_COUNT_TOLERANCE,
    MAX_REVISION_ATTEMPTS,
)
from app.logger import setup_logger
from app.prompts import SYSTEM_PROMPT, build_prompt


logger = setup_logger()


class ContentGenerationError(Exception):
    """Ошибка, которую можно безопасно показать пользователю."""


def count_words(text: str) -> int:
    """Подсчитывает слова на русском и английском языках."""

    words = re.findall(
        r"[^\W\d_]+(?:[-’'][^\W\d_]+)*",
        text,
        flags=re.UNICODE,
    )

    return len(words)


def _request_gigachat(messages: list[Messages]) -> str:
    """Отправляет запрос в GigaChat и возвращает полученный текст."""

    payload = Chat(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        repetition_penalty=REPETITION_PENALTY,
        max_tokens=MAX_TOKENS,
    )

    try:
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            model=MODEL_NAME,
            verify_ssl_certs=False,
        ) as giga:
            response = giga.chat(payload)

    except AuthenticationError as error:
        logger.error("Ошибка авторизации GigaChat")
        raise ContentGenerationError(
            "Не удалось авторизоваться в GigaChat. "
            "Проверьте учётные данные в файле .env."
        ) from error

    except ForbiddenError as error:
        logger.error("Доступ к модели или сервису GigaChat запрещён")
        raise ContentGenerationError(
            "У вашего аккаунта нет доступа к запрошенной модели или сервису."
        ) from error

    except RateLimitError as error:
        logger.warning("Превышен лимит запросов GigaChat")

        retry_after = error.retry_after

        if retry_after > 0:
            message = (
                f"Превышен лимит запросов GigaChat. "
                f"Попробуйте снова через {retry_after:g} сек."
            )
        else:
            message = (
                "Превышен лимит запросов или доступная квота GigaChat. "
                "Попробуйте позже или проверьте ограничения аккаунта."
            )

        raise ContentGenerationError(message) from error

    except BadRequestError as error:
        logger.error("GigaChat отклонил запрос")
        raise ContentGenerationError(
            "GigaChat отклонил запрос. "
            "Проверьте параметры генерации и попробуйте снова."
        ) from error

    except NotFoundError as error:
        logger.error("Модель или ресурс GigaChat не найдены")
        raise ContentGenerationError(
            "Запрошенная модель или ресурс GigaChat не найдены. "
            "Проверьте настройки приложения."
        ) from error

    except RequestEntityTooLargeError as error:
        logger.error("Размер запроса превышает допустимый лимит")
        raise ContentGenerationError(
            "Запрос слишком большой. "
            "Попробуйте сократить тему или объём публикации."
        ) from error

    except UnprocessableEntityError as error:
        logger.error("GigaChat не смог обработать запрос")
        raise ContentGenerationError(
            "GigaChat не смог обработать запрос. "
            "Попробуйте изменить тему или параметры публикации."
        ) from error

    except ServerError as error:
        logger.error("Ошибка на стороне сервера GigaChat")
        raise ContentGenerationError(
            "На стороне GigaChat произошла ошибка. Попробуйте позже."
        ) from error

    except ResponseError as error:
        logger.error(
            "Ошибка ответа GigaChat: HTTP %s",
            error.status_code,
        )
        raise ContentGenerationError(
            "GigaChat вернул ошибку при обработке запроса. Попробуйте позже."
        ) from error

    except LengthFinishReasonError as error:
        logger.warning("Ответ модели был обрезан из-за ограничения длины")
        raise ContentGenerationError(
            "Ответ модели оказался слишком длинным и был обрезан. "
            "Попробуйте уменьшить желаемый объём публикации."
        ) from error

    except ModelNotSpecifiedError as error:
        logger.error("Не указана модель GigaChat")
        raise ContentGenerationError(
            "Не указана модель GigaChat. Проверьте настройки приложения."
        ) from error

    except GigaChatException as error:
        logger.exception("Неизвестная ошибка SDK GigaChat")
        raise ContentGenerationError(
            "Произошла ошибка при взаимодействии с GigaChat."
        ) from error

    except httpx.TimeoutException as error:
        logger.warning("Превышено время ожидания ответа GigaChat")
        raise ContentGenerationError(
            "Превышено время ожидания ответа GigaChat. Попробуйте ещё раз."
        ) from error

    except httpx.TransportError as error:
        logger.error("Ошибка соединения с GigaChat")
        raise ContentGenerationError(
            "Не удалось установить соединение с GigaChat. "
            "Проверьте подключение к интернету и попробуйте снова."
        ) from error

    if not response.choices:
        logger.warning("GigaChat вернул ответ без вариантов генерации")
        raise ContentGenerationError(
            "Модель не вернула вариантов ответа. Попробуйте ещё раз."
        )

    text = response.choices[0].message.content

    if not text or not text.strip():
        logger.warning("GigaChat вернул пустой ответ")
        raise ContentGenerationError(
            "Модель вернула пустой текст. "
            "Измените тему или объём и запросите публикацию ещё раз."
        )

    return text.strip()


def _build_revision_prompt(
    text: str,
    actual_count: int,
    target_count: int,
    min_words: int,
    max_words: int,
) -> str:
    """Формирует задание на исправление объёма публикации."""

    if actual_count < min_words:
        instruction = (
            "Текст короче необходимого. Расширь публикацию до требуемого "
            "объёма, добавив полезные подробности и раскрывая тему глубже. "
            "Не повторяй уже изложенные мысли и не добавляй вымышленные факты."
        )
    else:
        instruction = (
            "Текст длиннее необходимого. Сократи публикацию до требуемого "
            "объёма, убрав повторы и второстепенные детали. "
            "Сохрани основные мысли и смысл."
        )

    return (
        "Исправь объём уже подготовленной публикации.\n\n"
        f"ЖЕЛАЕМЫЙ ОБЪЁМ: около {target_count} слов.\n"
        f"ДОПУСТИМЫЙ ДИАПАЗОН: от {min_words} до {max_words} слов.\n"
        f"ТЕКУЩИЙ ОБЪЁМ: {actual_count} слов.\n\n"
        f"{instruction}\n\n"
        "Верни только исправленную публикацию, без пояснений.\n\n"
        "ТЕКУЩАЯ ПУБЛИКАЦИЯ:\n"
        f"{text}"
    )


def generate_content(
    topic: str,
    platform: str,
    tone: str,
    word_count: int,
) -> str:
    """Генерирует публикацию и корректирует её объём при необходимости."""

    logger.info(
        "Начало генерации: platform=%s, tone=%s, word_count=%s",
        platform,
        tone,
        word_count,
    )

    min_words = math.ceil(
        word_count * (1 - WORD_COUNT_TOLERANCE)
    )
    max_words = math.floor(
        word_count * (1 + WORD_COUNT_TOLERANCE)
    )

    messages = [
        Messages(
            role=MessagesRole.SYSTEM,
            content=SYSTEM_PROMPT,
        ),
        Messages(
            role=MessagesRole.USER,
            content=build_prompt(topic, platform, tone, word_count),
        ),
    ]

    best_text = ""
    best_difference = float("inf")

    for attempt in range(MAX_REVISION_ATTEMPTS + 1):
        text = _request_gigachat(messages)
        actual_count = count_words(text)

        difference = abs(actual_count - word_count)

        logger.info(
            "Попытка %s: получено %s слов, целевой объём — %s",
            attempt + 1,
            actual_count,
            word_count,
        )

        if difference < best_difference:
            best_text = text
            best_difference = difference

        if min_words <= actual_count <= max_words:
            logger.info(
                "Объём публикации соответствует требованиям: %s слов",
                actual_count,
            )
            return text

        if attempt < MAX_REVISION_ATTEMPTS:
            logger.info(
                "Объём не соответствует требованиям. "
                "Запрашивается корректировка."
            )

            messages.append(
                Messages(
                    role=MessagesRole.ASSISTANT,
                    content=text,
                )
            )

            messages.append(
                Messages(
                    role=MessagesRole.USER,
                    content=_build_revision_prompt(
                        text=text,
                        actual_count=actual_count,
                        target_count=word_count,
                        min_words=min_words,
                        max_words=max_words,
                    ),
                )
            )

    logger.warning(
        "Не удалось добиться требуемого объёма после %s попыток. "
        "Возвращается наиболее подходящий вариант.",
        MAX_REVISION_ATTEMPTS + 1,
    )

    logger.info(
        "Генерация завершена: words=%s, characters=%s",
        count_words(best_text),
        len(best_text),
    )

    return best_text
