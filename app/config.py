import os

from dotenv import load_dotenv

# Подхватываем переменные из .env в окружение процесса.
load_dotenv()

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
MODEL_NAME = "GigaChat-3-Lightning"

if not GIGACHAT_CREDENTIALS:
    raise ValueError(
        "Ключ GIGACHAT_CREDENTIALS не найден. "
        "Добавьте его в файл .env."
    )
