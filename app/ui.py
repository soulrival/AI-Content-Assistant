
import sqlite3

import streamlit as st

from app.database import (
    delete_generation,
    get_generations,
    init_db,
    save_generation,
)
from app.generator import (
    ContentGenerationError,
    count_words,
    generate_content,
)


def _reuse_generation(
    topic: str,
    platform: str,
    tone: str,
    word_count: int,
) -> None:
    """Переносит параметры сохранённой генерации в форму."""

    st.session_state["topic_input"] = topic
    st.session_state["platform_input"] = platform
    st.session_state["tone_input"] = tone
    st.session_state["word_count_input"] = word_count
    st.session_state["section"] = "Генератор"
    st.session_state["history_notice"] = (
        "Параметры загружены. Можешь изменить их и запустить генерацию."
    )


def _delete_generation(generation_id: int) -> None:
    """Удаляет запись из истории."""

    if delete_generation(generation_id):
        st.session_state["history_notice"] = "Запись удалена из истории."
    else:
        st.session_state["history_notice"] = (
            "Не удалось найти эту запись. Возможно, она уже удалена."
        )


def _show_generator() -> None:
    """Отображает форму генерации и результат."""

    st.subheader("Параметры публикации")

    with st.form("generation_form"):
        topic = st.text_area(
            "Тема публикации",
            placeholder="Например: Как искусственный интеллект меняет образование",
            height=110,
            key="topic_input",
        )

        col1, col2 = st.columns(2)

        with col1:
            platform = st.selectbox(
                "Платформа",
                options=["Telegram", "VK"],
                key="platform_input",
            )

        with col2:
            tone = st.selectbox(
                "Тональность",
                options=[
                    "нейтральная",
                    "дружелюбная",
                    "профессиональная",
                ],
                key="tone_input",
            )

        word_count = st.number_input(
            "Желаемое количество слов",
            min_value=10,
            max_value=1000,
            value=120,
            step=10,
            key="word_count_input",
        )

        submitted = st.form_submit_button(
            "Сгенерировать публикацию",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.pop("generated_text", None)
        st.session_state.pop("generation_settings", None)

        if not topic.strip():
            st.warning("Введите тему публикации.")
        else:
            try:
                with st.spinner(
                    "GigaChat готовит публикацию. "
                    "Это может занять несколько секунд..."
                ):
                    result = generate_content(
                        topic=topic.strip(),
                        platform=platform,
                        tone=tone,
                        word_count=int(word_count),
                    )

                actual_count = count_words(result)

                st.session_state["generated_text"] = result
                st.session_state["generation_settings"] = {
                    "topic": topic.strip(),
                    "platform": platform,
                    "tone": tone,
                    "word_count": int(word_count),
                    "actual_word_count": actual_count,
                }

                try:
                    save_generation(
                        topic=topic.strip(),
                        generated_text=result,
                        platform=platform,
                        tone=tone,
                        target_word_count=int(word_count),
                        actual_word_count=actual_count,
                    )
                    st.session_state["history_notice"] = (
                        "Публикация успешно сохранена в истории."
                    )
                except sqlite3.Error:
                    st.warning(
                        "Публикация создана, но не удалось сохранить "
                        "её в истории."
                    )

            except ContentGenerationError as error:
                st.error(str(error))

    generated_text = st.session_state.get("generated_text")

    if generated_text:
        st.divider()
        st.subheader("Результат генерации")

        settings = st.session_state["generation_settings"]
        actual_count = count_words(generated_text)

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Количество слов", actual_count)
            st.caption(
                f"Желаемый объём: {settings['word_count']} слов"
            )

        with col2:
            st.metric("Платформа", settings["platform"])
            st.caption(
                f"Тональность: {settings['tone']}"
            )

        st.code(
            generated_text,
            language=None,
            wrap_lines=True,
        )

        st.caption(
            "Чтобы скопировать публикацию, нажмите на значок "
            "копирования в правом верхнем углу текстового блока."
        )


def _show_history() -> None:
    """Отображает сохранённые генерации."""

    st.subheader("История генераций")

    generations = get_generations()

    if not generations:
        st.info(
            "История пока пуста. Создай первую публикацию в разделе "
            "«Генератор»."
        )
        return

    st.caption(f"Всего сохранено публикаций: {len(generations)}")

    for generation in generations:
        topic_preview = generation["topic"].strip()

        if len(topic_preview) > 65:
            topic_preview = topic_preview[:65] + "..."

        title = (
            f"#{generation['id']} — {topic_preview}"
        )

        with st.expander(title):
            st.caption(
                f"Дата создания: {generation['created_at']}"
            )

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "Платформа",
                    generation["platform"],
                )
                st.caption(
                    f"Тональность: {generation['tone']}"
                )

            with col2:
                st.metric(
                    "Количество слов",
                    generation["actual_word_count"],
                )
                st.caption(
                    "Желаемый объём: "
                    f"{generation['target_word_count']} слов"
                )

            st.markdown("**Тема:**")
            st.write(generation["topic"])

            st.markdown("**Текст публикации:**")
            st.code(
                generation["generated_text"],
                language=None,
                wrap_lines=True,
            )

            col1, col2 = st.columns(2)

            with col1:
                st.button(
                    "Использовать параметры",
                    key=f"reuse_{generation['id']}",
                    use_container_width=True,
                    on_click=_reuse_generation,
                    args=(
                        generation["topic"],
                        generation["platform"],
                        generation["tone"],
                        generation["target_word_count"],
                    ),
                )

            with col2:
                st.button(
                    "Удалить",
                    key=f"delete_{generation['id']}",
                    use_container_width=True,
                    on_click=_delete_generation,
                    args=(generation["id"],),
                )


def run_app() -> None:
    """Запускает веб-интерфейс генератора публикаций."""

    st.set_page_config(
        page_title="AI Content Assistant",
        page_icon="✍️",
        layout="centered",
    )

    init_db()

    st.title("✍️ AI Content Assistant")
    st.caption(
        "Генератор публикаций для социальных сетей "
        "на основе искусственного интеллекта"
    )

    if "history_notice" in st.session_state:
        st.info(st.session_state.pop("history_notice"))

    section = st.sidebar.radio(
        "Раздел приложения",
        options=["Генератор", "История"],
        key="section",
    )

    if section == "Генератор":
        _show_generator()
    else:
        _show_history()
