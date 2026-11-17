
import sqlite3

import streamlit as st

from app.database import (
    delete_edit,
    delete_generation,
    get_edits,
    get_generations,
    init_db,
    save_edit,
    save_generation,
)
from app.editor import (
    AVAILABLE_TONES,
    EDIT_ACTIONS,
    edit_content,
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


def _load_text_into_editor(
    text: str,
    source_generation_id: int | None = None,
) -> None:
    """Передаёт текст в AI-редактор."""

    st.session_state["editor_source_text"] = text
    st.session_state["editor_source_generation_id"] = source_generation_id
    st.session_state["section"] = "AI-редактор"
    st.session_state.pop("editor_result", None)
    st.session_state["history_notice"] = (
        "Текст загружен в AI-редактор. Выбери режим обработки."
    )


def _replace_editor_source() -> None:
    """Заменяет исходный текст результатом редактирования."""

    result = st.session_state.get("editor_result")

    if result:
        st.session_state["editor_source_text"] = result
        st.session_state.pop("editor_result", None)
        st.session_state["history_notice"] = (
            "Исходный текст заменён результатом редактирования."
        )


def _delete_generation(generation_id: int) -> None:
    """Удаляет запись из истории генераций."""

    if delete_generation(generation_id):
        st.session_state["history_notice"] = "Запись удалена из истории."
    else:
        st.session_state["history_notice"] = (
            "Не удалось найти эту запись. Возможно, она уже удалена."
        )


def _delete_edit(edit_id: int) -> None:
    """Удаляет запись из истории редактирований."""

    if delete_edit(edit_id):
        st.session_state["history_notice"] = (
            "Результат редактирования удалён из истории."
        )
    else:
        st.session_state["history_notice"] = (
            "Не удалось найти эту запись. Возможно, она уже удалена."
        )


def _show_generator() -> None:
    """Отображает форму генерации и результат."""

    st.subheader("Параметры публикации")

    # Значение по умолчанию задаётся через Session State.
    # Это предотвращает конфликт с обновлением значения из callback.
    st.session_state.setdefault("word_count_input", 120)

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
                options=AVAILABLE_TONES,
                key="tone_input",
            )

        word_count = st.number_input(
            "Желаемое количество слов",
            min_value=10,
            max_value=1000,
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

        st.button(
            "Передать текст в AI-редактор",
            type="primary",
            use_container_width=True,
            on_click=_load_text_into_editor,
            args=(generated_text,),
        )



def _show_editor() -> None:
    """Отображает интерфейс AI-редактора."""

    st.subheader("AI-редактор")
    st.write(
        "Обработай готовый текст: улучши стиль, исправь ошибки, "
        "измени объём или задай собственную инструкцию."
    )

    st.session_state.setdefault("editor_source_text", "")
    st.session_state.setdefault("editor_action", "improve")

    source_text = st.text_area(
        "Исходный текст",
        height=260,
        placeholder="Вставь сюда текст, который нужно отредактировать...",
        key="editor_source_text",
    )

    action = st.selectbox(
        "Режим редактирования",
        options=list(EDIT_ACTIONS.keys()),
        format_func=lambda value: EDIT_ACTIONS[value],
        key="editor_action",
    )

    tone = None
    custom_instruction = ""

    # Дополнительные поля отображаются сразу после выбора режима.
    if action == "change_tone":
        tone = st.selectbox(
            "Новая тональность",
            options=AVAILABLE_TONES,
            key="editor_tone",
        )

    elif action == "custom":
        custom_instruction = st.text_area(
            "Своя инструкция",
            height=100,
            placeholder=(
                "Например: Сделай текст более убедительным, "
                "но сохрани его дружелюбный тон."
            ),
            key="editor_custom_instruction",
        )

    submitted = st.button(
        "Обработать текст",
        type="primary",
        use_container_width=True,
    )

    if submitted:
        st.session_state.pop("editor_result", None)

        if not source_text.strip():
            st.warning("Сначала введи исходный текст.")

        elif action == "custom" and not custom_instruction.strip():
            st.warning("Введи инструкцию для редактирования.")

        else:
            try:
                with st.spinner(
                    "GigaChat редактирует текст. "
                    "Это может занять несколько секунд..."
                ):
                    result = edit_content(
                        text=source_text,
                        action=action,
                        custom_instruction=custom_instruction,
                        tone=tone,
                    )

                st.session_state["editor_result"] = result

                try:
                    save_edit(
                        source_text=source_text,
                        edited_text=result,
                        action=action,
                        action_label=EDIT_ACTIONS[action],
                        actual_word_count=count_words(result),
                        tone=tone,
                        custom_instruction=custom_instruction,
                        source_generation_id=st.session_state.get(
                            "editor_source_generation_id"
                        ),
                    )
                    st.session_state["history_notice"] = (
                        "Результат редактирования сохранён в истории."
                    )
                except sqlite3.Error:
                    st.warning(
                        "Текст отредактирован, но не удалось "
                        "сохранить результат в истории."
                    )

            except (ContentGenerationError, ValueError) as error:
                st.error(str(error))

    edited_text = st.session_state.get("editor_result")

    if edited_text:
        st.divider()
        st.subheader("Результат редактирования")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Количество слов", count_words(edited_text))

        with col2:
            st.metric(
                "Режим",
                EDIT_ACTIONS.get(
                    st.session_state.get("editor_action"),
                    "Редактирование",
                ),
            )

        st.code(
            edited_text,
            language=None,
            wrap_lines=True,
        )

        st.caption(
            "Исходный текст не изменяется автоматически. "
            "При необходимости ты можешь заменить его результатом."
        )

        st.button(
            "Заменить исходный текст результатом",
            type="primary",
            use_container_width=True,
            on_click=_replace_editor_source,
        )



def _show_history() -> None:
    """Отображает историю генераций и редактирований."""

    st.subheader("История")

    generations = get_generations()
    edits = get_edits()

    if not generations and not edits:
        st.info(
            "История пока пуста. Создай первую публикацию "
            "или отредактируй готовый текст."
        )
        return

    st.caption(
        f"Генераций: {len(generations)} · "
        f"Редактирований: {len(edits)}"
    )

    if generations:
        st.markdown("### Генерации")

        for generation in generations:
            topic_preview = generation["topic"].strip()

            if len(topic_preview) > 65:
                topic_preview = topic_preview[:65] + "..."

            title = f"#{generation['id']} — {topic_preview}"

            with st.expander(title):
                st.caption(
                    f"Дата создания: {generation['created_at']}"
                )

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Платформа", generation["platform"])
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

                col1, col2, col3 = st.columns(3)

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
                        "Редактировать",
                        key=f"edit_generation_{generation['id']}",
                        use_container_width=True,
                        on_click=_load_text_into_editor,
                        args=(
                            generation["generated_text"],
                            generation["id"],
                        ),
                    )

                with col3:
                    st.button(
                        "Удалить",
                        key=f"delete_generation_{generation['id']}",
                        use_container_width=True,
                        on_click=_delete_generation,
                        args=(generation["id"],),
                    )

    if edits:
        st.markdown("### Редактирования")

        for edit in edits:
            title = (
                f"#{edit['id']} — {edit['action_label']} "
                f"({edit['actual_word_count']} слов)"
            )

            with st.expander(title):
                st.caption(
                    f"Дата создания: {edit['created_at']}"
                )

                st.markdown("**Исходный текст:**")
                st.code(
                    edit["source_text"],
                    language=None,
                    wrap_lines=True,
                )

                st.markdown("**Результат:**")
                st.code(
                    edit["edited_text"],
                    language=None,
                    wrap_lines=True,
                )

                if edit["tone"]:
                    st.caption(
                        f"Выбранная тональность: {edit['tone']}"
                    )

                if edit["custom_instruction"]:
                    st.caption(
                        "Пользовательская инструкция: "
                        f"{edit['custom_instruction']}"
                    )

                col1, col2 = st.columns(2)

                with col1:
                    st.button(
                        "Продолжить редактирование",
                        key=f"reuse_edit_{edit['id']}",
                        use_container_width=True,
                        on_click=_load_text_into_editor,
                        args=(edit["edited_text"],),
                    )

                with col2:
                    st.button(
                        "Удалить",
                        key=f"delete_edit_{edit['id']}",
                        use_container_width=True,
                        on_click=_delete_edit,
                        args=(edit["id"],),
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

    section = st.radio(
        "Раздел приложения",
        options=["Генератор", "AI-редактор", "История"],
        horizontal=True,
        label_visibility="collapsed",
        key="section",
    )

    st.divider()

    if section == "Генератор":
        _show_generator()
    elif section == "AI-редактор":
        _show_editor()
    else:
        _show_history()
