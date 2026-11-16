from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from app.config import GIGACHAT_CREDENTIALS, MODEL_NAME
from app.prompts import SYSTEM_PROMPT, build_prompt


def generate_content(topic: str, platform: str, tone: str, word_count: int) -> str:
    """Отправляет задание в GigaChat и возвращает текст публикации."""
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

    with GigaChat(
        credentials=GIGACHAT_CREDENTIALS,
        model=MODEL_NAME,
        verify_ssl_certs=False,
    ) as giga:
        response = giga.chat(payload)

    text = response.choices[0].message.content
    if not text or not text.strip():
        raise ValueError(
            "Модель вернула пустой текст. "
            "Измените тему или объём и запросите публикацию ещё раз."
        )

    return text
