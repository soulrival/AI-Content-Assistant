
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
from app.prompts import (
    DEFAULT_PUBLICATION_GOAL,
    DEFAULT_TARGET_AUDIENCE,
    PUBLICATION_GOALS,
    TARGET_AUDIENCES,
)


def _apply_custom_styles() -> None:
    """Применяет дополнительные стили интерфейса."""

    st.markdown(
        """
        <style>
        :root {
            --app-bg: #1D1825;
            --purple: #A98AD6;
            --purple-hover: #BDA4E3;
            --teal: #69B9B0;
            --text-main: #F0EAF5;
            --text-muted: #B8AFC4;
            --blue: #83B8EF;
            --yellow: #E7C16F;
            --red: #E18A8A;
        }

        [data-testid="stAppViewContainer"] {
            background: var(--app-bg);
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 940px;
            padding-top: 2.2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        h1, h2, h3 {
            color: var(--text-main);
            letter-spacing: -0.035em;
        }

        h1 {
            font-weight: 750 !important;
        }

        h2, h3 {
            font-weight: 650 !important;
        }

        [data-testid="stCaptionContainer"],
        [data-testid="stMarkdownContainer"] small {
            color: var(--text-muted);
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid rgba(189, 164, 227, 0.22) !important;
            border-radius: 14px !important;
            background: rgba(41, 35, 51, 0.78);
        }

        [data-testid="stExpander"] {
            border: 1px solid rgba(189, 164, 227, 0.22) !important;
            border-radius: 12px !important;
            background: rgba(41, 35, 51, 0.42);
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] > div > div {
            border-radius: 9px !important;
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stNumberInput"] input:focus,
        [data-testid="stSelectbox"] > div > div:focus-within {
            border-color: var(--purple) !important;
            box-shadow: 0 0 0 1px rgba(169, 138, 214, 0.35) !important;
        }

        [data-testid="stBaseButton-primary"],
        [data-testid="stBaseButton-secondary"] {
            border-radius: 10px !important;
            font-weight: 600 !important;
            transition:
                background 0.18s ease,
                border-color 0.18s ease,
                color 0.18s ease,
                box-shadow 0.18s ease;
        }

        [data-testid="stBaseButton-primary"] {
            background: #604A7A !important;
            border-color: var(--purple) !important;
            color: #FFFFFF !important;
        }

        [data-testid="stBaseButton-primary"]:hover {
            background: #71588F !important;
            border-color: var(--purple-hover) !important;
            box-shadow: 0 0 0 2px rgba(189, 164, 227, 0.13);
        }

        [data-testid="stBaseButton-secondary"] {
            border-color: rgba(189, 164, 227, 0.38) !important;
            color: #D9CDE8 !important;
            background: rgba(52, 43, 64, 0.45) !important;
        }

        [data-testid="stBaseButton-secondary"]:hover {
            border-color: var(--purple) !important;
            color: #FFFFFF !important;
            background: rgba(169, 138, 214, 0.13) !important;
        }

        /* Навигация */

        .st-key-nav_generator button,
        .st-key-nav_editor button,
        .st-key-nav_history button {
            min-height: 3.2rem;
            width: 100%;
            border-radius: 12px !important;
            font-size: 0.94rem;
            font-weight: 650 !important;
        }

        .st-key-nav_generator button[data-testid="stBaseButton-secondary"] {
            border-color: rgba(169, 138, 214, 0.55) !important;
            color: #D5C5E9 !important;
        }

        .st-key-nav_generator button[data-testid="stBaseButton-primary"] {
            background: #514064 !important;
            border-color: var(--purple) !important;
            color: #FFFFFF !important;
        }

        .st-key-nav_editor button[data-testid="stBaseButton-secondary"] {
            border-color: rgba(105, 185, 176, 0.55) !important;
            color: #9CCBC5 !important;
        }

        .st-key-nav_editor button[data-testid="stBaseButton-primary"] {
            background: #294541 !important;
            border-color: var(--teal) !important;
            color: #E5F5F2 !important;
        }

        .st-key-nav_editor button[data-testid="stBaseButton-secondary"]:hover {
            border-color: var(--teal) !important;
            color: #D9F2ED !important;
            background: rgba(105, 185, 176, 0.12) !important;
            box-shadow: 0 0 14px rgba(105, 185, 176, 0.1);
        }

        .st-key-nav_history button[data-testid="stBaseButton-secondary"] {
            border-color: rgba(180, 154, 216, 0.32) !important;
            color: #BDB0CE !important;
        }

        .st-key-nav_history button[data-testid="stBaseButton-primary"] {
            background: #443750 !important;
            border-color: #B49AD8 !important;
            color: #F0EAF5 !important;
        }

        /* Параметры — синие */

        [class*="st-key-reuse_"] button {
            color: var(--blue) !important;
            border-color: rgba(131, 184, 239, 0.72) !important;
            background: rgba(54, 91, 126, 0.20) !important;
        }

        [class*="st-key-reuse_"] button:hover {
            color: #D8EBFF !important;
            border-color: var(--blue) !important;
            background: rgba(54, 91, 126, 0.36) !important;
        }

        /* Редактирование — жёлтое */

        [class*="st-key-edit_generation_"] button,
        [class*="st-key-reuse_edit_"] button {
            color: var(--yellow) !important;
            border-color: rgba(231, 193, 111, 0.72) !important;
            background: rgba(116, 87, 34, 0.20) !important;
        }

        [class*="st-key-edit_generation_"] button:hover,
        [class*="st-key-reuse_edit_"] button:hover {
            color: #FFF0C9 !important;
            border-color: var(--yellow) !important;
            background: rgba(116, 87, 34, 0.36) !important;
        }

        /* Удаление — красное */

        [class*="st-key-delete_generation_"] button,
        [class*="st-key-delete_edit_"] button {
            color: var(--red) !important;
            border-color: rgba(225, 138, 138, 0.72) !important;
            background: rgba(117, 48, 48, 0.20) !important;
        }

        [class*="st-key-delete_generation_"] button:hover,
        [class*="st-key-delete_edit_"] button:hover {
            color: #FFE1E1 !important;
            border-color: var(--red) !important;
            background: rgba(117, 48, 48, 0.38) !important;
        }

        [data-testid="stMetric"] {
            background: rgba(52, 43, 64, 0.72);
            border: 1px solid rgba(189, 164, 227, 0.24);
            border-radius: 10px;
            padding: 0.85rem 1rem;
        }

        [data-testid="stCode"] {
            border-radius: 10px !important;
        }

        hr {
            border-color: rgba(189, 164, 227, 0.18) !important;
        }

        [data-testid="stAlert"] {
            border-radius: 10px;
        }

        @media (max-width: 768px) {
            [data-testid="stMainBlockContainer"] {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1.4rem;
            }

            .st-key-nav_generator button,
            .st-key-nav_editor button,
            .st-key-nav_history button {
                min-height: 2.8rem;
                font-size: 0.8rem;
                padding-left: 0.2rem;
                padding-right: 0.2rem;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            *,
            *::before,
            *::after {
                transition-duration: 0.01ms !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _reuse_generation(
    topic: str,
    platform: str,
    tone: str,
    word_count: int,
    target_audience: str | None = None,
    publication_goal: str | None = None,
    additional_wishes: str | None = None,
) -> None:
    """Переносит параметры сохранённой генерации в форму."""

    st.session_state["topic_input"] = topic
    st.session_state["platform_input"] = platform
    st.session_state["tone_input"] = tone
    st.session_state["word_count_input"] = word_count

    st.session_state["target_audience_input"] = (
        target_audience or DEFAULT_TARGET_AUDIENCE
    )
    st.session_state["publication_goal_input"] = (
        publication_goal or DEFAULT_PUBLICATION_GOAL
    )
    st.session_state["additional_wishes_input"] = (
        additional_wishes or ""
    )

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


def _request_delete(record_type: str, record_id: int) -> None:
    """Запрашивает подтверждение перед удалением записи."""

    st.session_state["pending_delete"] = {
        "type": record_type,
        "id": record_id,
    }


@st.dialog("Подтверждение удаления")
def _show_delete_confirmation() -> None:
    """Показывает диалог подтверждения удаления."""

    pending = st.session_state.get("pending_delete")

    if not pending:
        st.info("Запись для удаления не выбрана.")
        return

    st.warning(
        "Ты действительно хочешь удалить эту запись из истории?\n\n"
        "Это действие нельзя будет отменить."
    )

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        if st.button(
            "Удалить",
            type="primary",
            use_container_width=True,
            key="confirm_delete_record",
        ):
            if pending["type"] == "generation":
                deleted = delete_generation(pending["id"])
                message = "Запись удалена из истории."
            else:
                deleted = delete_edit(pending["id"])
                message = "Результат редактирования удалён из истории."

            st.session_state["history_notice"] = (
                message
                if deleted
                else "Не удалось найти эту запись. Возможно, она уже удалена."
            )

            st.session_state.pop("pending_delete", None)
            st.rerun()

    with cancel_col:
        if st.button(
            "Отмена",
            use_container_width=True,
            key="cancel_delete_record",
        ):
            st.session_state.pop("pending_delete", None)
            st.rerun()


def _show_word_count_status(
    word_count: int,
    is_valid: bool | int | None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:
    """Показывает количество слов и статус проверки объёма."""

    if is_valid is None:
        st.markdown(f"**Количество слов:** {word_count}")
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


def _show_navigation() -> str:
    """Отображает навигацию между разделами приложения."""

    sections = [
        ("Генератор", "🪄  Генератор", "nav_generator"),
        ("AI-редактор", "✍️  AI-редактор", "nav_editor"),
        ("История", "◷  История", "nav_history"),
    ]

    current_section = st.session_state.get("section", "Генератор")
    columns = st.columns(3)

    for column, (section, label, key) in zip(columns, sections):
        with column:
            if st.button(
                label,
                key=key,
                type=(
                    "primary"
                    if current_section == section
                    else "secondary"
                ),
                use_container_width=True,
            ):
                st.session_state["section"] = section
                st.rerun()

    return st.session_state.get("section", "Генератор")


def _show_generator() -> None:
    """Отображает форму генерации и полученные варианты."""

    st.subheader("Параметры публикации")

    st.session_state.setdefault("word_count_input", 120)
    st.session_state.setdefault("variant_count_input", 4)
    st.session_state.setdefault(
        "target_audience_input",
        DEFAULT_TARGET_AUDIENCE,
    )
    st.session_state.setdefault(
        "publication_goal_input",
        DEFAULT_PUBLICATION_GOAL,
    )
    st.session_state.setdefault("additional_wishes_input", "")

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

        with st.expander("Дополнительные настройки", expanded=False):
            target_audience = st.selectbox(
                "Целевая аудитория",
                options=TARGET_AUDIENCES,
                key="target_audience_input",
            )

            publication_goal = st.selectbox(
                "Цель публикации",
                options=PUBLICATION_GOALS,
                key="publication_goal_input",
            )

            additional_wishes = st.text_area(
                "Дополнительные пожелания",
                placeholder=(
                    "Например: избегай сложных терминов, "
                    "добавь конкретный пример..."
                ),
                height=100,
                key="additional_wishes_input",
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
                        target_audience=target_audience,
                        publication_goal=publication_goal,
                        additional_wishes=additional_wishes.strip(),
                    )

                generation_settings = {
                    "topic": topic.strip(),
                    "platform": platform,
                    "tone": tone,
                    "word_count": int(word_count),
                    "target_audience": target_audience,
                    "publication_goal": publication_goal,
                    "additional_wishes": additional_wishes.strip(),
                }

                try:
                    generation_ids = save_generations(
                        topic=topic.strip(),
                        platform=platform,
                        tone=tone,
                        target_word_count=int(word_count),
                        variants=variants,
                        target_audience=target_audience,
                        publication_goal=publication_goal,
                        additional_wishes=additional_wishes.strip(),
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

            except (ContentGenerationError, ValueError) as error:
                st.error(str(error))

    generated_variants = st.session_state.get("generated_variants")

    if generated_variants:
        st.divider()
        st.subheader(
            f"Результаты генерации ({len(generated_variants)} вариантов)"
        )

        settings = st.session_state["generation_settings"]

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Количество вариантов", len(generated_variants))
            st.caption(
                f"Желаемый объём: {settings['word_count']} слов"
            )

        with col2:
            st.metric("Платформа", settings["platform"])
            st.caption(f"Тональность: {settings['tone']}")

        st.markdown(f"**Тема:** {settings['topic']}")

        st.caption(
            f"Аудитория: {settings['target_audience']} · "
            f"Цель: {settings['publication_goal']}"
        )

        if settings["additional_wishes"]:
            st.caption(
                f"Дополнительные пожелания: "
                f"{settings['additional_wishes']}"
            )

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
                    st.metric("Стиль", variant["label"])

                st.code(
                    variant["text"],
                    language=None,
                    wrap_lines=True,
                )

                st.button(
                    "Редактировать",
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
            "Для копирования текста используй значок копирования "
            "в правом верхнем углу блока с публикацией."
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
                "target_audience": generation.get("target_audience"),
                "publication_goal": generation.get("publication_goal"),
                "additional_wishes": generation.get("additional_wishes"),
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
                st.caption(f"Дата создания: {group['created_at']}")

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

                if group.get("target_audience"):
                    st.caption(
                        f"Аудитория: {group['target_audience']}"
                    )

                if group.get("publication_goal"):
                    st.caption(
                        f"Цель: {group['publication_goal']}"
                    )

                if group.get("additional_wishes"):
                    st.caption(
                        "Дополнительные пожелания: "
                        f"{group['additional_wishes']}"
                    )

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
                        st.metric("ID записи", generation["id"])

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
                                group.get("target_audience"),
                                group.get("publication_goal"),
                                group.get("additional_wishes"),
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
                            on_click=_request_delete,
                            args=("generation", generation["id"]),
                        )

    if edits:
        st.markdown("### Редактирования")

        for edit in edits:
            title = (
                f"#{edit['id']} — {edit['action_label']} "
                f"({edit['actual_word_count']} слов)"
            )

            with st.expander(title):
                st.caption(f"Дата создания: {edit['created_at']}")

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
                        on_click=_request_delete,
                        args=("edit", edit["id"]),
                    )


def run_app() -> None:
    """Запускает веб-интерфейс генератора публикаций."""

    st.set_page_config(
        page_title="AI Content Assistant",
        page_icon="✍️",
        layout="wide",
    )

    _apply_custom_styles()
    init_db()

    st.title("✍️ AI Content Assistant")
    st.caption(
        "Генератор публикаций для социальных сетей "
        "на основе искусственного интеллекта"
    )

    if "history_notice" in st.session_state:
        st.info(st.session_state.pop("history_notice"))

    st.session_state.setdefault("section", "Генератор")

    section = _show_navigation()

    st.divider()

    if section == "Генератор":
        _show_generator()
    elif section == "AI-редактор":
        _show_editor()
    else:
        _show_history()

    if st.session_state.get("pending_delete"):
        _show_delete_confirmation()
