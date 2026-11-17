
import os

from dotenv import load_dotenv

# Подхватываем переменные из .env в окружение процесса.
load_dotenv()

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
MODEL_NAME = "GigaChat-3-Lightning"

# Параметры генерации текста.
TEMPERATURE = 0.7
TOP_P = 0.9
REPETITION_PENALTY = 1.1
MAX_TOKENS = 2000

# Настройки контроля объёма публикации.
WORD_COUNT_TOLERANCE = 0.1
MAX_REVISION_ATTEMPTS = 2

if not GIGACHAT_CREDENTIALS:
    raise ValueError(
        "Ключ GIGACHAT_CREDENTIALS не найден. "
        "Добавьте его в файл .env."
    )
