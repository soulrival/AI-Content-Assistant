
from app.generator import ContentGenerationError, generate_content

PLATFORMS = ("Telegram", "VK")
TONES = ("нейтральная", "дружелюбная", "профессиональная")
MIN_WORD_COUNT = 10
MAX_WORD_COUNT = 1000


def ask_non_empty(prompt: str) -> str:
    """Спрашивает строку, пока пользователь не введёт непустой текст."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Тема не может быть пустой. Попробуйте ещё раз.")


def ask_choice(prompt: str, options: tuple[str, ...]) -> str:
    """Показывает нумерованный список и возвращает выбранный вариант."""
    print(prompt)
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")

    while True:
        raw_value = input("Номер: ").strip()
        if raw_value.isdigit():
            number = int(raw_value)
            if 1 <= number <= len(options):
                return options[number - 1]
        print("Введите номер из списка.")


def ask_word_count() -> int:
    """Спрашивает целое число слов в диапазоне от 10 до 1000."""
    while True:
        raw_value = input("Желаемое количество слов: ").strip()
        if not raw_value.isdigit() or int(raw_value) <= 0:
            print("Введите положительное целое число, например 200.")
            continue

        word_count = int(raw_value)
        if word_count < MIN_WORD_COUNT or word_count > MAX_WORD_COUNT:
            print(
                f"Объём должен быть от {MIN_WORD_COUNT} до {MAX_WORD_COUNT} слов. "
                "Попробуйте ещё раз."
            )
            continue

        return word_count


def main() -> None:
    topic = ask_non_empty("Тема публикации: ")
    platform = ask_choice("Платформа:", PLATFORMS)
    tone = ask_choice("Тональность:", TONES)
    word_count = ask_word_count()

    print("\nГенерирую публикацию...\n")

    try:
        text = generate_content(topic, platform, tone, word_count)
    except ContentGenerationError as error:
        print(f"Ошибка генерации: {error}")
        return

    print(text)


if __name__ == "__main__":
    main()
