import sqlite3

import streamlit as st

from app.database import (
    delete_edit,
    delete_generation,
    get_edits,
    get_generations,
    init_db,
    save_edit,
    save_generations,
)
from app.editor import (
    AVAILABLE_TONES,
    EDIT_ACTIONS,
    edit_content,
)
from app.generator import (
    ContentGenerationError,
    count_words,
    generate_variants,
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


def _show_word_count_status(
    word_count: int,
    is_valid: bool | int | None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:
    """Показывает количество слов и статус проверки объёма."""

    if is_valid is None:
        st.markdown("**Количество слов:** " f"{word_count}")
        st.caption("Статус не сохранён для этой записи.")
        return

    if bool(is_valid):
        st.markdown(
            f"**Количество слов:** {word_count} "
            ":green[· Точный]"
        )
    else:
        st.markdown(
            f"**Количество слов:** :red[{word_count} · Неточный]"
        )

    if minimum is not None and maximum is not None:
        st.caption(
            f"Допустимый диапазон: от {minimum} до {maximum} слов."
        )


def _show_generator() -> None:
    """Отображает форму генерации и полученные варианты."""

    st.subheader("Параметры публикации")

    st.session_state.setdefault("word_count_input", 120)
    st.session_state.setdefault("variant_count_input", 4)

    with st.form("generation_form"):
        topic = st.text_area(
            "Тема публикации",
            placeholder=(
                "Например: Как искусственный интеллект меняет образование"
            ),
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

        col1, col2 = st.columns(2)

        with col1:
            word_count = st.number_input(
                "Желаемое количество слов",
                min_value=10,
                max_value=1000,
                step=10,
                key="word_count_input",
            )

        with col2:
            variant_count = st.number_input(
                "Количество вариантов",
                min_value=1,
                max_value=4,
                step=1,
                key="variant_count_input",
            )

        st.caption(
            "Варианты будут отличаться способом подачи материала, "
            "но сохранят выбранные тему, платформу и тональность."
        )

        submitted = st.form_submit_button(
            "Сгенерировать варианты",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.pop("generated_variants", None)
        st.session_state.pop("generation_settings", None)

        if not topic.strip():
            st.warning("Введите тему публикации.")
        else:
            try:
                with st.spinner(
                    "GigaChat готовит варианты публикации. "
                    "Это может занять некоторое время..."
                ):
                    variants = generate_variants(
                        topic=topic.strip(),
                        platform=platform,
                        tone=tone,
                        word_count=int(word_count),
                        variant_count=int(variant_count),
                    )

                generation_settings = {
                    "topic": topic.strip(),
                    "platform": platform,
                    "tone": tone,
                    "word_count": int(word_count),
                }

                try:
                    generation_ids = save_generations(
                        topic=topic.strip(),
                        platform=platform,
                        tone=tone,
                        target_word_count=int(word_count),
                        variants=variants,
                    )

                    for variant, generation_id in zip(
                        variants,
                        generation_ids,
                    ):
                        variant["generation_id"] = generation_id

                    st.session_state["history_notice"] = (
                        f"Все {len(variants)} варианта успешно сохранены "
                        "в истории."
                    )

                except sqlite3.Error:
                    st.warning(
                        "Варианты созданы, но не удалось сохранить "
                        "их в истории."
                    )

                    for variant in variants:
                        variant["generation_id"] = None

                st.session_state["generated_variants"] = variants
                st.session_state["generation_settings"] = (
                    generation_settings
                )

            except ContentGenerationError as error:
                st.error(str(error))

    generated_variants = st.session_state.get("generated_variants")

    if generated_variants:
        st.divider()
        st.subheader("Результаты генерации")

        settings = st.session_state["generation_settings"]

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Количество вариантов",
                len(generated_variants),
            )
            st.caption(
                f"Желаемый объём: {settings['word_count']} слов"
            )

        with col2:
            st.metric("Платформа", settings["platform"])
            st.caption(f"Тональность: {settings['tone']}")

        st.markdown(f"**Тема:** {settings['topic']}")

        for index, variant in enumerate(generated_variants, start=1):
            with st.container(border=True):
                st.markdown(
                    f"**Вариант {index}. {variant['label']}**"
                )

                st.caption(variant["description"])

                col1, col2 = st.columns(2)

                with col1:
                    _show_word_count_status(
                        word_count=variant["word_count"],
                        is_valid=variant.get("is_valid"),
                        minimum=variant.get("min_word_count"),
                        maximum=variant.get("max_word_count"),
                    )

                with col2:
                    st.metric(
                        "Стиль",
                        variant["label"],
                    )

                st.code(
                    variant["text"],
                    language=None,
                    wrap_lines=True,
                )

                st.button(
                    "Передать этот вариант в AI-редактор",
                    key=f"edit_variant_{index}",
                    type="primary",
                    use_container_width=True,
                    on_click=_load_text_into_editor,
                    args=(
                        variant["text"],
                        variant.get("generation_id"),
                    ),
                )

        st.caption(
            "Чтобы скопировать публикацию, нажмите на значок "
            "копирования в правом верхнем углу текстового блока."
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


def _group_generations(generations: list) -> list:
    """Объединяет варианты одной генерации для отображения в истории."""

    groups = {}
    ordered_groups = []

    for generation in generations:
        group_id = generation["variant_group_id"]

        if group_id is None:
            group_key = f"legacy-{generation['id']}"
        else:
            group_key = group_id

        if group_key not in groups:
            group = {
                "id": group_key,
                "topic": generation["topic"],
                "platform": generation["platform"],
                "tone": generation["tone"],
                "target_word_count": generation["target_word_count"],
                "created_at": generation["created_at"],
                "variants": [],
            }

            groups[group_key] = group
            ordered_groups.append(group)

        groups[group_key]["variants"].append(generation)

    return ordered_groups


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
        f"Вариантов генерации: {len(generations)} · "
        f"Редактирований: {len(edits)}"
    )

    if generations:
        st.markdown("### Генерации")

        generation_groups = _group_generations(generations)

        for group in generation_groups:
            topic_preview = group["topic"].strip()

            if len(topic_preview) > 65:
                topic_preview = topic_preview[:65] + "..."

            variant_count = len(group["variants"])

            variant_word = (
                "вариант"
                if variant_count == 1
                else "варианта"
                if variant_count < 5
                else "вариантов"
            )

            title = (
                f"{topic_preview} "
                f"({variant_count} {variant_word})"
            )

            with st.expander(title):
                st.caption(
                    f"Дата создания: {group['created_at']}"
                )

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Платформа", group["platform"])
                    st.caption(f"Тональность: {group['tone']}")

                with col2:
                    st.metric("Вариантов", variant_count)
                    st.caption(
                        "Желаемый объём: "
                        f"{group['target_word_count']} слов"
                    )

                st.markdown("**Тема:**")
                st.write(group["topic"])

                for index, generation in enumerate(
                    group["variants"],
                    start=1,
                ):
                    st.divider()

                    style_label = generation["style_label"]

                    if style_label:
                        st.markdown(
                            f"**Вариант {index}. {style_label}**"
                        )
                    else:
                        st.markdown(f"**Вариант {index}**")

                    if generation["style_description"]:
                        st.caption(
                            generation["style_description"]
                        )

                    col1, col2 = st.columns(2)

                    with col1:
                        _show_word_count_status(
                            word_count=generation["actual_word_count"],
                            is_valid=generation.get("is_valid"),
                            minimum=generation.get("min_word_count"),
                            maximum=generation.get("max_word_count"),
                        )

                    with col2:
                        st.metric(
                            "ID записи",
                            generation["id"],
                        )

                    st.code(
                        generation["generated_text"],
                        language=None,
                        wrap_lines=True,
                    )

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.button(
                            "Параметры",
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