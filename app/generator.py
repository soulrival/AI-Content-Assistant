
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

from app.config import GIGACHAT_CREDENTIALS, MODEL_NAME
from app.logger import setup_logger
from app.prompts import SYSTEM_PROMPT, build_prompt


logger = setup_logger()


class ContentGenerationError(Exception):
    """Ошибка, которую можно безопасно показать пользователю."""


def generate_content(
    topic: str,
    platform: str,
    tone: str,
    word_count: int,
) -> str:
    """Отправляет задание в GigaChat и возвращает текст публикации."""

    logger.info(
        "Начало генерации: platform=%s, tone=%s, word_count=%s",
        platform,
        tone,
        word_count,
    )

    payload = Chat(
        model=MODEL_NAME,
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
            Messages(
                role=MessagesRole.USER,
                content=build_prompt(topic, platform, tone, word_count),
            ),
        ],
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
            "Запрос слишком большой. Попробуйте сократить тему или объём публикации."
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

    text = response.choices[0].message.content

    if not text or not text.strip():
        logger.warning("GigaChat вернул пустой ответ")
        raise ContentGenerationError(
            "Модель вернула пустой текст. "
            "Измените тему или объём и запросите публикацию ещё раз."
        )

    logger.info("Генерация успешно завершена")

    return text
