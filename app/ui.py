import streamlit as st

from app.generator import (
    ContentGenerationError,
    count_words,
    generate_content,
)


def run_app() -> None:
    """Запускает веб-интерфейс генератора публикаций."""

    st.set_page_config(
        page_title="AI Content Assistant",
        page_icon="✍️",
        layout="centered",
    )

    st.title("✍️ AI Content Assistant")
    st.caption(
        "Генератор публикаций для социальных сетей "
        "на основе искусственного интеллекта"
    )

    st.divider()
    st.subheader("Параметры публикации")

    with st.form("generation_form"):
        topic = st.text_area(
            "Тема публикации",
            placeholder="Например: Как искусственный интеллект меняет образование",
            height=110,
        )

        col1, col2 = st.columns(2)

        with col1:
            platform = st.selectbox(
                "Платформа",
                options=["Telegram", "VK"],
            )

        with col2:
            tone = st.selectbox(
                "Тональность",
                options=[
                    "нейтральная",
                    "дружелюбная",
                    "профессиональная",
                ],
            )

        word_count = st.number_input(
            "Желаемое количество слов",
            min_value=10,
            max_value=1000,
            value=120,
            step=10,
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

                st.session_state["generated_text"] = result
                st.session_state["generation_settings"] = {
                    "platform": platform,
                    "tone": tone,
                    "word_count": int(word_count),
                }

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