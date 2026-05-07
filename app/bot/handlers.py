"""Обработчики сообщений для Telegram бота — МАРШРУТИЗАЦИЯ"""

import asyncio
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.agent.hr_agent import HRAgent
from app.utils.file_parser import parse_resume
from app.services.hr_facade import HRAgentFacade
from app.core.config import settings
from .middlewares import get_role, is_hr, get_user_id

from .commands import start
from .pagination import handle_pagination_callback
from .documents import handle_document
from .candidates import (
    handle_candidate_addition, handle_job_addition,
    handle_editing_candidate, handle_editing_job,
    show_candidate_info, show_job_info,
    show_candidates_list, show_jobs_list,
    export_candidate_to_pdf_command, export_job_to_pdf_command,
    confirm_delete_candidate, confirm_delete_all_candidates, confirm_delete_all_jobs
)
from .surveys import (
    create_survey_command, analyze_survey_command,
    show_surveys_list, delete_survey_command,
    nps_chart_command, pulse_chart_command, chart_command,
    confirm_delete_all_surveys
)
from .tests_onboarding import (
    handle_test_generation, handle_editing_test,
    export_test_pdf_command, export_onboarding_pdf_command,
    handle_onboarding_start, handle_onboarding_role,
    handle_onboarding_level, handle_onboarding_date,
    handle_editing_onboarding
)
from .keyboards import (
    get_main_keyboard, get_vacancies_keyboard, get_candidates_keyboard,
    get_surveys_keyboard, get_cancel_keyboard, get_candidate_keyboard,
    get_slots_management_keyboard, get_slots_calendar_inline_keyboard,
    get_slots_time_keyboard
)
from .states import (
    CANCEL_WORDS, CANDIDATE_ADD_WORDS, JOB_ADD_WORDS,
    PARSING_YES_WORDS, PARSING_NO_WORDS, PARSING_UPDATE_WORDS,
    TEST_TRIGGERS, ONBOARDING_TRIGGERS,
    SURVEY_CREATE_TRIGGERS, SURVEY_ANALYZE_TRIGGERS,
    SURVEY_DELETE_TRIGGERS, SURVEY_DELETE_ALL_TRIGGERS, SURVEY_LIST_TRIGGERS,
    CHART_TRIGGERS, SURVEY_NPS_CHART_TRIGGERS, SURVEY_PULSE_CHART_TRIGGERS,
    JOB_EXPORT_PDF_TRIGGERS, CANDIDATE_EXPORT_PDF_TRIGGERS,
    CANDIDATE_LIST_TRIGGERS, CANDIDATE_INFO_TRIGGERS,
    CANDIDATE_DELETE_TRIGGERS, CANDIDATE_DELETE_ALL_TRIGGERS, CANDIDATE_EDIT_TRIGGERS,
    CANDIDATE_RESTORE_TRIGGERS,
    JOB_LIST_TRIGGERS, JOB_INFO_TRIGGERS,
    JOB_DELETE_TRIGGERS, JOB_DELETE_ALL_TRIGGERS, JOB_EDIT_TRIGGERS,
    JOB_ARCHIVE_TRIGGERS, JOB_ACTIVATE_TRIGGERS,
    TEST_EXPORT_PDF_TRIGGERS, ONBOARDING_EXPORT_PDF_TRIGGERS,
    TEST_EDIT_TRIGGERS, ONBOARDING_EDIT_TRIGGERS,
    STATISTICS_TRIGGERS, CANDIDATE_EXPORT_EXCEL_TRIGGERS,
    DIRECTION_NAMES, DEPARTMENT_MAP, DEPT_NAMES,
)
from .utils import clear_user_state as old_clear_user_state, format_years

logger = get_logger(__name__)


def _is_parsing_command(text: str, commands: list[str]) -> bool:
    """Проверяет команды подтверждения парсинга только целиком, без совпадений внутри слов."""
    text_lower = text.lower().strip()
    return any(re.fullmatch(rf"{re.escape(command)}[.!?]*", text_lower) for command in commands)


def _looks_like_invite_command(text: str) -> bool:
    """Определяет команду приглашения, включая частые опечатки в слове 'пригласить'."""
    text_lower = text.lower()
    return bool(
        re.search(r'\bпригл[а-я]*\b', text_lower)
        or re.search(r'\binvite\b', text_lower)
        or re.search(r'\bкандидата\s+\d+\s+на\s+собеседование\b', text_lower)
    )


def _normalize_position_for_search(position: str) -> str:
    """Приводит простые русские формы должностей к виду, который лучше ищется."""
    position = position.lower().replace("ё", "е")
    position = re.sub(r'\s+', ' ', position).strip(" .,!?:;")

    normalized_words = []
    for word in position.split():
        parts = []
        for part in word.split("-"):
            if len(part) > 4 and part.endswith(("а", "у", "я")):
                part = part[:-1]
            parts.append(part)
        normalized_words.append("-".join(parts))

    return " ".join(normalized_words).strip()


def _extract_search_position_for_invite(text: str) -> Optional[str]:
    """Достаёт должность из цепочки вроде 'найди инженера и пригласи его'."""
    text_lower = text.lower().replace("ё", "е")

    has_search = any(keyword in text_lower for keyword in ["найди", "найти", "ищу", "поиск", "подбери"])
    has_pronoun_invite = re.search(
        r'\bпригл[а-я]*\s+(?:его|ее|их|лучшего|подходящего)\s+на\s+собеседование\b',
        text_lower,
    )
    if not has_search or not has_pronoun_invite:
        return None

    query = re.sub(r'\bи\s+пригл[а-я]*\b.*$', '', text_lower).strip()
    query = re.sub(r'\bпригл[а-я]*\b.*$', '', query).strip()

    for keyword in ["найди мне", "найди", "найти", "ищу", "поиск", "подбери"]:
        query = query.replace(keyword, " ")

    query = re.sub(r'\b(?:кандидата|кандидатов|сотрудника|специалиста|человека)\b', " ", query)
    query = re.sub(r'\b(?:на|для|по|с|со|и)\b', " ", query)
    query = re.sub(r'\s+', ' ', query).strip(" .,!?:;")

    if len(query) < 3:
        return None

    return _normalize_position_for_search(query)


def _is_confirm_action(text: str) -> bool:
    text_lower = text.lower().strip()
    return text_lower in {"да", "подтвердить", "подтверждаю", "отправить", "отправь", "ок", "окей"}


def _is_reject_action(text: str) -> bool:
    text_lower = text.lower().strip()
    return text_lower in {"нет", "не надо", "отмена", "отменить", "не отправлять"}


def _get_hr_agent(context: ContextTypes.DEFAULT_TYPE) -> Optional[HRAgent]:
    """Возвращает общий HRAgent из bot_data и кэширует его в user_data."""
    agent = context.user_data.get("hr_agent")
    if agent:
        return agent

    agent = getattr(context, "bot_data", {}).get("hr_agent")
    if agent:
        context.user_data["hr_agent"] = agent
        return agent

    return None


async def _chat_with_hr_agent(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> str:
    """Запускает синхронный LLM-клиент вне event loop Telegram с историей диалога."""
    agent = _get_hr_agent(context)
    if not agent:
        raise RuntimeError("HR agent не инициализирован в bot_data")

    telegram_id = context.user_data.get("user_id", 0)
    history = HRAgentFacade.get_recent_conversation_history(telegram_id, limit=10) if telegram_id else []
    response = await asyncio.to_thread(
        agent.chat,
        text,
        history=history,
        session_data=context.user_data,
    )

    if telegram_id:
        HRAgentFacade.save_conversation_message(telegram_id, "user", text)
        HRAgentFacade.save_conversation_message(telegram_id, "assistant", response)

    return response


def _cleanup_temp_file(file_path: Optional[str]) -> None:
    if file_path and Path(file_path).exists():
        try:
            os.unlink(file_path)
        except OSError as e:
            logger.warning(f"Не удалось удалить временный файл {file_path}: {e}")


def _remember_candidate_context(context: ContextTypes.DEFAULT_TYPE, candidate: Optional[Dict[str, Any]]) -> None:
    """Запоминает последнего релевантного кандидата для фраз вроде 'пригласи его'."""
    if candidate:
        context.user_data["last_candidate"] = candidate


def _remember_candidates_context(context: ContextTypes.DEFAULT_TYPE, candidates: List[Dict[str, Any]]) -> None:
    if candidates:
        context.user_data["last_candidates"] = candidates[:10]
        _remember_candidate_context(context, candidates[0])


def _remember_job_context(context: ContextTypes.DEFAULT_TYPE, job: Optional[Dict[str, Any]]) -> None:
    """Запоминает последнюю вакансию для фраз вроде 'создай тест для этой вакансии'."""
    if job:
        context.user_data["last_job"] = job


def _save_dialog_turn(
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    assistant_text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Сохраняет важный командный ответ в историю для следующих LLM-запросов."""
    telegram_id = context.user_data.get("user_id", 0)
    if not telegram_id:
        return
    HRAgentFacade.save_conversation_message(telegram_id, "user", user_text, metadata)
    HRAgentFacade.save_conversation_message(telegram_id, "assistant", assistant_text, metadata)


def _looks_like_context_invite(text: str) -> bool:
    text_lower = text.lower()
    return (
        any(word in text_lower for word in ["пригласи", "пригласить", "приглашение"])
        and any(word in text_lower for word in ["его", "ее", "её", "этого кандидата"])
    )


async def _prepare_invite_for_last_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    candidate = context.user_data.get("last_candidate")
    if not candidate:
        return False

    candidate_id = candidate.get("id")
    candidate_name = candidate.get("name", "Без имени")
    if not candidate_id:
        return False

    fresh_candidate = HRAgentFacade.get_candidate(candidate_id) or candidate
    if fresh_candidate.get("interview_stage") in ["invited", "scheduled"]:
        await update.message.reply_text(f"❌ Кандидат {candidate_name} уже приглашён на собеседование")
        return True

    position = (context.user_data.get("last_job") or {}).get("title") or fresh_candidate.get("last_position")
    context.user_data["pending_action"] = {
        "type": "invite_candidate_to_interview",
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "position": position,
    }
    position_text = f"\n• Должность: {position}" if position else ""
    await update.message.reply_text(
        "📅 **Подготовлено приглашение на собеседование**\n\n"
        f"• Кандидат: **{candidate_name}**\n"
        f"• ID: {candidate_id}"
        f"{position_text}\n\n"
        "Подтвердите отправку: напишите **да**, **подтвердить** или **отправить**.\n"
        "Чтобы отменить действие, напишите **нет** или **отмена**.",
        reply_markup=get_main_keyboard()
    )
    return True


async def _generate_test_for_last_job(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    job = context.user_data.get("last_job")
    if not job:
        return False

    from app.services.test_generator import generate_test, format_test

    status_msg = await update.message.reply_text(
        f"🔄 **Генерация тестового задания**\n\n"
        f"💼 Вакансия: {job.get('title', '—')}\n\n"
        f"⏳ Пожалуйста, подождите..."
    )
    test = generate_test(
        direction="custom",
        level=job.get("level") or "middle",
        tech_stack=job.get("skills", []),
        candidate_name=job.get("title"),
    )
    await status_msg.delete()

    if "error" in test:
        await update.message.reply_text(f"❌ Ошибка: {test['error']}", reply_markup=get_main_keyboard())
        return True

    temp_data_local = context.user_data.get("temp_data", {})
    temp_data_local["last_test"] = test
    context.user_data["temp_data"] = temp_data_local
    formatted = format_test(test)
    formatted += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    formatted += "\n📌 **Чтобы сохранить тест в PDF, напишите:**"
    formatted += "\n   • `экспорт теста в pdf`"
    formatted += "\n   • `сохранить тест в pdf имя_файла.pdf`"
    formatted += "\n\n✏️ **Чтобы отредактировать тест, напишите:**"
    formatted += "\n   • `редактировать тест`"
    formatted += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(formatted, parse_mode="Markdown", reply_markup=get_main_keyboard())
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()


    is_hr_user = settings.is_hr(user_id)

    if is_hr_user:
        context.user_data["role"] = "hr"
        context.user_data["is_hr"] = True
    else:
        context.user_data["role"] = "candidate"
        context.user_data["is_hr"] = False
    context.user_data["user_id"] = user_id

    if getattr(context, "bot_data", {}).get("hr_agent"):
        context.user_data["hr_agent"] = context.bot_data["hr_agent"]

    final_is_hr = context.user_data.get("is_hr", is_hr_user)

    logger.info(f"👤 Пользователь {user_id} (is_hr={final_is_hr}): {text}")

    if not final_is_hr:
        HRAgentFacade.register_candidate(user_id, update.effective_user.first_name)

        from app.bot.onboarding_flow import process_onboarding_message
        if await process_onboarding_message(update, context):
            return

        if text.lower() == "отменить собеседование":
            from app.bot.interview_flow import cancel_candidate_interview
            await cancel_candidate_interview(update, context)
            return

        if text.lower() == "изменить время":
            from app.bot.interview_flow import change_interview_time
            await change_interview_time(update, context)
            return

        if text == "📋 Смотреть вакансии":
            jobs = HRAgentFacade.get_all_jobs(active_only=True)

            if not jobs:
                await update.message.reply_text(
                    "📭 На данный момент нет открытых вакансий.\n\n"
                    "Загляните позже!",
                    reply_markup=get_candidate_keyboard()
                )
                return

            output = ["💼 **Активные вакансии:**", ""]
            for job in jobs:
                output.append(f"**{job.get('title', '—')}**")
                output.append(f"   • Уровень: {job.get('level', '—')}")
                output.append(f"   • Опыт: {job.get('experience', 0)} лет")
                if job.get('skills'):
                    skills = job.get('skills', [])[:5]
                    output.append(f"   • Навыки: {', '.join(skills)}")
                output.append("")

            await update.message.reply_text(
                "\n".join(output),
                reply_markup=get_candidate_keyboard()
            )
            return

        if update.message.document:
            document = update.message.document
            file_name = document.file_name or ""
            file_ext = Path(file_name).suffix.lower()

            if file_ext not in ['.pdf', '.docx']:
                await update.message.reply_text("❌ Пожалуйста, отправьте файл в формате PDF или DOCX")
                return

            await update.message.reply_text(f"📄 Получил {file_name}\n🔄 Сохраняю резюме...")

            file = await document.get_file()
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name

            parsed = parse_resume(tmp_path)

            if "error" in parsed:
                await update.message.reply_text(f"❌ Ошибка: {parsed['error']}")
                os.unlink(tmp_path)
                return

            parsed['telegram_id'] = user_id

            candidate_id = HRAgentFacade.save_candidate(parsed, tmp_path)
            candidate_name = parsed.get('name', 'Не указано')
            last_position = parsed.get('last_position', '')

            if not HRAgentFacade.is_candidate_in_notification_queue(candidate_id):
                HRAgentFacade.add_to_notification_queue(candidate_id, candidate_name, last_position)
                logger.info(f"✅ Кандидат {candidate_id} добавлен в очередь уведомлений")
            else:
                logger.info(f"⏭️ Кандидат {candidate_id} уже есть в очереди, пропускаем")

            os.unlink(tmp_path)

            await update.message.reply_text(
                "✅ **Спасибо! Ваше резюме принято.**\n\n"
                "Мы рассмотрим его и свяжемся с вами при наличии подходящих вакансий.\n\n"
                "Хорошего дня! 🙌",
                reply_markup=get_candidate_keyboard()
            )
            return

        if text and not text.startswith("/"):
            try:
                await update.message.chat.send_action(action="typing")
                status_msg = await update.message.reply_text("🤔 Думаю...")

                from openai import OpenAI
                temp_agent = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.openrouter_api_key,
                    timeout=settings.llm_timeout
                )

                candidate_prompt = """Ты — дружелюбный помощник для соискателей. Ты помогаешь кандидатам отвечать на вопросы о процессе отбора, собеседованиях, вакансиях.

Ты НЕ HR-агент. Ты НЕ можешь управлять резюме, вакансиями, опросами.

Твои возможности:
- Отвечать на общие вопросы о процессе найма
- Объяснять, как пользоваться ботом
- Давать советы по подготовке к собеседованию

Если кандидат спрашивает про конкретные действия (отмена, изменение времени), направь его:
- "отменить собеседование" — чтобы отменить запись
- "изменить время" — чтобы выбрать новое время

Будь вежливым, полезным и дружелюбным. Отвечай на русском языке.

Если вопрос не по теме или ты не знаешь ответа, предложи обратиться к HR."""

                response = temp_agent.chat.completions.create(
                    model=settings.default_model,
                    messages=[
                        {"role": "system", "content": candidate_prompt},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.7,
                    timeout=settings.llm_timeout
                )

                answer = response.choices[0].message.content or "Не могу ответить. Попробуйте спросить иначе."

                await status_msg.delete()
                if len(answer) > 4000:
                    for i in range(0, len(answer), 4000):
                        await update.message.reply_text(answer[i:i+4000])
                else:
                    await update.message.reply_text(answer, reply_markup=get_candidate_keyboard())
            except Exception as e:
                logger.error(f"Ошибка при вызове LLM: {e}")
                await status_msg.edit_text("😕 Не могу ответить. Попробуйте позже.")
            return

        if text == "📄 Отправить резюме" or text:
            await update.message.reply_text(
                "📄 **Отправка резюме**\n\n"
                "Вы можете отправить ваше резюме в формате **PDF** или **DOCX**.\n\n"
                "✅ Резюме будет автоматически добавлено в базу кандидатов.\n"
                "✅ HR рассмотрит его и свяжется с вами при наличии подходящих вакансий.\n\n"
                "Просто отправьте файл в этот чат.",
                reply_markup=get_candidate_keyboard()
            )
            return

    if text.lower() in CANCEL_WORDS or text == "❌ Отмена":
        if context.user_data.get("user_state"):
            context.user_data["user_state"] = {}
        if context.user_data.get("temp_data"):
            context.user_data["temp_data"] = {}
        context.user_data.pop("pending_action", None)
        await update.message.reply_text("✅ Отменено", reply_markup=get_main_keyboard())
        return

    if text == "◀️ Назад в главное меню":
        if context.user_data.get("user_state"):
            context.user_data["user_state"] = {}
        if context.user_data.get("temp_data"):
            context.user_data["temp_data"] = {}
        context.user_data.pop("pending_action", None)
        await update.message.reply_text("Главное меню:", reply_markup=get_main_keyboard())
        return


    pending_action = context.user_data.get("pending_action")
    if pending_action and pending_action.get("type") == "invite_candidate_to_interview":
        if _is_confirm_action(text):
            from app.bot.interview_flow import send_invite_to_candidate

            candidate_id = pending_action.get("candidate_id")
            candidate_name = pending_action.get("candidate_name", "Без имени")
            position = pending_action.get("position")
            context.user_data.pop("pending_action", None)
            await send_invite_to_candidate(update, candidate_id, candidate_name, position)
            return

        if _is_reject_action(text):
            context.user_data.pop("pending_action", None)
            await update.message.reply_text("✅ Отправка приглашения отменена", reply_markup=get_main_keyboard())
            return

    if _looks_like_context_invite(text):
        if await _prepare_invite_for_last_candidate(update, context):
            return


    if text.lower().startswith("восстановить из архива"):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            if not HRAgentFacade.is_candidate_archived(candidate_id):
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден в архиве")
                return

            archived_list = HRAgentFacade.get_archived_candidates(limit=100)
            candidate_name = "кандидата"
            for cand in archived_list:
                if cand.get('id') == candidate_id:
                    candidate_name = cand.get('name', 'кандидата')
                    break

            if HRAgentFacade.restore_from_archive(candidate_id):
                await update.message.reply_text(
                    f"✅ Кандидат **{candidate_name}** (ID: {candidate_id}) восстановлен из архива",
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(f"❌ Не удалось восстановить кандидата")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'восстановить из архива 1'")
        return


    if text == "📅 Управление собеседованиями":
        await update.message.reply_text(
            "📅 **Управление слотами для собеседований**\n\n"
            "Выберите действие:",
            reply_markup=get_slots_management_keyboard()
        )
        return

    if text == "📅 Добавить день":
        await update.message.reply_text(
            "📅 **Выберите дату, на которую добавить слоты на весь день:**\n\n"
            "Будут созданы слоты с 09:00 до 18:00 с шагом 1 час",
            reply_markup=get_slots_calendar_inline_keyboard(hr_id=user_id)
        )
        return

    if text == "📋 Мои слоты":
        from app.bot.schedule_manager import cmd_my_slots
        await cmd_my_slots(update, context)
        return

    if text == "🗑️ Удалить слот":
        await update.message.reply_text(
            "🗑️ **Удаление слота**\n\n"
            "Введите ID слота для удаления.\n"
            "Узнать ID можно через '📋 Мои слоты'\n\n"
            "Пример: `удалить слот 1` или `/del_slot 1`"
        )
        return

    if text == "🗑️ Очистить дату":
        await update.message.reply_text(
            "🗑️ **Очистка даты**\n\n"
            "Выберите дату, на которой нужно удалить ВСЕ свободные слоты.\n"
            "Занятые слоты (где уже записан кандидат) НЕ будут удалены.\n\n"
            "📅 Выберите дату:",
            reply_markup=get_slots_calendar_inline_keyboard(hr_id=user_id)
        )
        context.user_data["temp_data"] = {"mode": "clear_date"}
        return


    match = re.search(r'удалить\s+слот\s+(\d+)', text.lower())
    if match:
        slot_id = int(match.group(1))
        from app.bot.schedule_manager import cmd_del_slot_text
        await cmd_del_slot_text(update, context, slot_id)
        return


    search_position_for_invite = _extract_search_position_for_invite(text)
    if search_position_for_invite:
        await update.message.chat.send_action(action="typing")
        status_msg = await update.message.reply_text("🤔 Подбираю кандидата и готовлю приглашение...")

        response = await _chat_with_hr_agent(context, text)
        await status_msg.delete()
        await update.message.reply_text(response, reply_markup=get_main_keyboard())
        return


    if _looks_like_invite_command(text):
        from app.bot.interview_flow import parse_invite_message, find_candidate_by_name, send_invite_to_candidate

        parsed = parse_invite_message(text)
        if not parsed:
            await update.message.reply_text(
                "❌ Не удалось распознать сообщение.\n\n"
                "Примеры:\n"
                "• пригласить Иванова Ивана на собеседование\n"
                "• пригласить кандидата 3 на собеседование"
            )
            return

        candidate_id = parsed.get("candidate_id")
        candidate_name = parsed.get("candidate_name")
        position = parsed.get("position")

        candidate = None

        if candidate_id:
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
                return
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name')
        elif candidate_name:
            candidate = find_candidate_by_name(candidate_name)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат '{candidate_name}' не найден в базе")
                return
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name')
        else:
            await update.message.reply_text("❌ Не удалось определить кандидата")
            return

        if candidate.get('interview_stage') in ['invited', 'scheduled']:
            await update.message.reply_text(f"❌ Кандидат {candidate_name} уже приглашён на собеседование")
            return

        context.user_data["pending_action"] = {
            "type": "invite_candidate_to_interview",
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "position": position,
        }
        position_text = f"\n• Должность: {position}" if position else ""
        await update.message.reply_text(
            "📅 **Подготовлено приглашение на собеседование**\n\n"
            f"• Кандидат: **{candidate_name}**\n"
            f"• ID: {candidate_id}"
            f"{position_text}\n\n"
            "Подтвердите отправку: напишите **да**, **подтвердить** или **отправить**.\n"
            "Чтобы отменить действие, напишите **нет** или **отмена**.",
            reply_markup=get_main_keyboard()
        )
        return


    if any(trigger in text.lower() for trigger in ["взять", "нанять", "предложить работу"]):
        from app.bot.offer_flow import parse_hire_message, find_candidate_by_name, send_offer_to_candidate

        parsed = parse_hire_message(text)
        if not parsed:
            await update.message.reply_text(
                "❌ Не удалось распознать сообщение.\n\n"
                "Примеры:\n"
                "• взять 14 на разработчика Python с зп 150000\n"
                "• взять Иванова Ивана на должность менеджера с зп 50000\n"
                "• нанять кандидата 1 на разработчика с зп 100000"
            )
            return

        candidate_id = parsed.get("candidate_id")
        candidate_name = parsed.get("candidate_name")
        position = parsed.get("position")
        salary = parsed.get("salary")

        candidate = None

        if candidate_id:
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
                return
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name')
        elif candidate_name:
            candidate = find_candidate_by_name(candidate_name)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат '{candidate_name}' не найден в базе")
                return
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name')
        else:
            await update.message.reply_text("❌ Не удалось определить кандидата")
            return

        if candidate.get('status') == 'hired':
            await update.message.reply_text(f"❌ Кандидат {candidate_name} уже нанят!")
            return

        success = await send_offer_to_candidate(update, candidate_id, candidate_name, position, salary)

        if success:
            pass
        return


    if any(trigger in text.lower() for trigger in ONBOARDING_EXPORT_PDF_TRIGGERS):
        if context.user_data.get("temp_data", {}).get("last_onboarding"):
            plan = context.user_data["temp_data"]["last_onboarding"]
            from app.utils.export import export_onboarding_to_pdf
            filename = export_onboarding_to_pdf(plan)
            if filename and Path(filename).exists():
                with open(filename, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=Path(filename).name,
                        caption="✅ План онбординга сохранён в PDF"
                    )
                os.unlink(filename)
            else:
                await update.message.reply_text("❌ Ошибка при создании PDF")
        else:
            await update.message.reply_text("❌ Сначала создайте план онбординга командой 'сделай онбординг'")
        return

    if any(trigger in text.lower() for trigger in TEST_EXPORT_PDF_TRIGGERS):
        if context.user_data.get("temp_data", {}).get("last_test"):
            test = context.user_data["temp_data"]["last_test"]
            from app.utils.export import export_test_to_pdf
            filename = export_test_to_pdf(test)
            if filename and Path(filename).exists():
                with open(filename, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=Path(filename).name,
                        caption="✅ Тестовое задание сохранено в PDF"
                    )
                os.unlink(filename)
            else:
                await update.message.reply_text("❌ Ошибка при создании PDF")
        else:
            await update.message.reply_text("❌ Сначала сгенерируйте тест командой 'создай тест'")
        return

    if any(trigger in text.lower() for trigger in JOB_EXPORT_PDF_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            job = HRAgentFacade.get_job(job_id)
            if job:
                from app.utils.export import export_job_to_pdf
                filename = export_job_to_pdf(job)
                if filename and Path(filename).exists():
                    with open(filename, 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename=Path(filename).name,
                            caption=f"✅ Карточка вакансии #{job_id}"
                        )
                    os.unlink(filename)
                else:
                    await update.message.reply_text("❌ Ошибка при создании PDF")
            else:
                await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'экспорт вакансии в pdf 1'")
        return

    if any(trigger in text.lower() for trigger in CANDIDATE_EXPORT_PDF_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if candidate:
                from app.utils.export import export_candidate_to_pdf
                filename = export_candidate_to_pdf(candidate)
                if filename and Path(filename).exists():
                    with open(filename, 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename=Path(filename).name,
                            caption=f"✅ Карточка кандидата #{candidate_id}"
                        )
                    os.unlink(filename)
                else:
                    await update.message.reply_text("❌ Ошибка при создании PDF")
            else:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'экспорт кандидата в pdf 1'")
        return


    if re.match(r'найди кандидата для вакансии\s+\d+', text.lower()) or re.match(r'подбери кандидатов для вакансии\s+\d+', text.lower()):
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            result = HRAgentFacade.match_candidates(job_id=job_id, top_n=10)

            if "error" in result:
                await update.message.reply_text(f"❌ {result['error']}")
                return

            job = result.get("job", {})
            candidates = result.get("top_candidates", [])
            _remember_job_context(context, job)
            _remember_candidates_context(context, candidates)

            if not candidates:
                await update.message.reply_text(f"😕 Подходящих кандидатов для вакансии '{job.get('title', '—')}' не найдено.")
                return

            output = [f"🎯 **ТОП КАНДИДАТОВ ДЛЯ ВАКАНСИИ: {job.get('title', '—')}**", ""]
            for i, cand in enumerate(candidates, 1):
                match_percent = cand.get('match_percent', cand.get('total_score', 0))
                if match_percent >= 70:
                    emoji = "🏆"
                elif match_percent >= 40:
                    emoji = "📊"
                else:
                    emoji = "⚠️"

                output.append(f"{emoji} **{i}. {cand.get('name', 'Без имени')}** — {match_percent}%")
                output.append(f"   • Опыт: {cand.get('experience_years', cand.get('experience', 0))} лет")
                if cand.get('skills'):
                    skills = cand.get('skills', [])[:5]
                    output.append(f"   • Навыки: {', '.join(skills)}")
                output.append("")

            response_text = "\n".join(output)
            _save_dialog_turn(context, text, response_text, {"type": "match_candidates_to_job", "job_id": job_id})
            await update.message.reply_text(response_text, reply_markup=get_main_keyboard())
            return


    if any(trigger in text.lower() for trigger in TEST_EDIT_TRIGGERS):
        if context.user_data.get("temp_data", {}).get("last_test"):
            context.user_data["user_state"] = {"state": "editing_test"}
            context.user_data["temp_data"]["edit_step"] = "direction"
            test = context.user_data["temp_data"]["last_test"]
            await update.message.reply_text(
                f"✏️ **Редактирование тестового задания**\n\n"
                f"Текущее направление: {test.get('direction', '—')}\n\n"
                f"Введите **новое направление** (it/production/construction/logistics/office/sales/marketing/finance/hr или backend/frontend и т.д.)\n"
                f"или '-' чтобы пропустить, 'отмена' для отмены",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await update.message.reply_text("❌ Сначала сгенерируйте тест командой 'создай тест'")
        return

    if any(trigger in text.lower() for trigger in ONBOARDING_EDIT_TRIGGERS):
        if context.user_data.get("temp_data", {}).get("last_onboarding"):
            context.user_data["user_state"] = {"state": "editing_onboarding"}
            context.user_data["temp_data"]["edit_step"] = "name"
            plan = context.user_data["temp_data"]["last_onboarding"]
            await update.message.reply_text(
                f"✏️ **Редактирование плана онбординга**\n\n"
                f"Текущее имя: {plan.get('candidate_name', '—')}\n\n"
                f"Введите **новое имя** сотрудника\n"
                f"или '-' чтобы пропустить, 'отмена' для отмены",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await update.message.reply_text("❌ Сначала создайте план онбординга командой 'сделай онбординг'")
        return


    if text == "📋 Вакансии":
        await update.message.reply_text("📋 **Управление вакансиями**\n\nВыберите действие:", reply_markup=get_vacancies_keyboard())
        return

    if text == "👥 Кандидаты":
        await update.message.reply_text("👥 **Управление кандидатами**\n\nВыберите действие:", reply_markup=get_candidates_keyboard())
        return
        
    if text == "📝 Создать тестирование":
        context.user_data["user_state"] = {"state": "test_waiting_for_direction"}
        await update.message.reply_text(
            "🎯 **Создание тестового задания**\n\nВведите **должность** или **направление** кандидата:\n"
            "Например: frontend разработчик, инженер-конструктор, бухгалтер, менеджер по продажам",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    if text == "📋 Создать онбординг":
        context.user_data["user_state"] = {"state": "onboarding_waiting_for_name"}
        await update.message.reply_text(
            "📋 **Создание плана онбординга**\n\nВведите **имя** сотрудника:",
            reply_markup=get_cancel_keyboard()
        )
        return

    if text == "📊 Опросы":
        await update.message.reply_text("📊 **Управление опросами**\n\nВыберите действие:", reply_markup=get_surveys_keyboard())
        return

    if text == "📈 Показать статистику":
        try:
            candidates = HRAgentFacade.get_all_candidates(limit=10000)
            jobs = HRAgentFacade.get_all_jobs(active_only=False)
            surveys = HRAgentFacade.get_all_surveys(active_only=False)
            total_responses = 0
            for s in surveys:
                total_responses += HRAgentFacade.get_survey_response_count(s["id"])

            active_jobs = len([j for j in jobs if j.get('status') == 'active'])
            archived_jobs = len([j for j in jobs if j.get('status') == 'archived'])

            stats_text = (
                f"📊 **СТАТИСТИКА**\n\n"
                f"👥 **Кандидаты:** {len(candidates)}\n"
                f"💼 **Вакансии:** {len(jobs)}\n"
                f"  • Активных: {active_jobs}\n"
                f"  • Архивных: {archived_jobs}\n"
                f"📋 **Опросы:** {len(surveys)}\n"
                f"  • Всего ответов: {total_responses}\n"
            )
            await update.message.reply_text(stats_text, reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"Ошибка статистики: {e}")
            await update.message.reply_text("📊 Статистика временно недоступна", reply_markup=get_main_keyboard())
        return


    if text == "📋 Показать все вакансии":
        await show_jobs_list(update)
        return

    if text == "📦 Архив вакансий":
        archived_jobs = HRAgentFacade.get_archived_jobs()
        if not archived_jobs:
            await update.message.reply_text("📭 Архив вакансий пуст", reply_markup=get_vacancies_keyboard())
            return

        output = ["📦 **АРХИВ ВАКАНСИЙ**", ""]
        for job in archived_jobs[:20]:
            level_icon = "🟢" if job.get('level') == 'junior' else "🟡" if job.get('level') == 'middle' else "🔴"
            output.append(f"📦 {level_icon} **#{job.get('id')}** — {job.get('title', '—')} ({job.get('level', '—')})")
            output.append(f"   • Опыт: {job.get('experience', 0)} лет")
            if job.get('skills'):
                output.append(f"   • Навыки: {', '.join(job.get('skills', [])[:5])}")
            output.append("")

        if len(archived_jobs) > 20:
            output.append(f"... и ещё {len(archived_jobs) - 20} архивных вакансий")

        output.append("💡 Чтобы вернуть вакансию: `активировать вакансию ID`")
        await update.message.reply_text("\n".join(output), reply_markup=get_vacancies_keyboard())
        return

    if text == "➕ Добавить новую вакансию":
        context.user_data["user_state"] = "job_waiting_for_title"
        context.user_data["temp_data"] = {}
        await update.message.reply_text(
            "💼 **Добавление вакансии**\n\nВведите **название**:",
            reply_markup=get_cancel_keyboard()
        )
        return


    if text == "👥 Показать всех кандидатов":
        await show_candidates_list(update, context=context)
        return
        
    if text == "➕ Добавить нового кандидата":
        context.user_data["user_state"] = {"state": "waiting_for_name"}
        await update.message.reply_text(
            "📝 **Добавление кандидата**\n\nВведите **ФИО**:",
            reply_markup=get_cancel_keyboard()
        )
        return

    if text == "🔍 Поиск кандидатов":
        await update.message.reply_text(
            "🔍 **Поиск кандидатов**\n\n"
            "Напишите запрос в свободной форме. Примеры:\n\n"
            "• `найди python разработчика`\n"
            "• `найди кандидата с Python и SQL`\n"
            "• `ищу frontend специалиста с опытом 3 года`\n"
            "• `найди инженера-конструктора`\n"
            "• `найди бухгалтера с опытом 5 лет`\n"
            "• `найди кандидата для вакансии 2`\n"
            "• `подбери кандидатов для вакансии 2`",
            reply_markup=get_cancel_keyboard()
        )
        return


    search_keywords = ["найди", "найти", "ищу", "поиск", "подбери", "найди мне"]
    if any(keyword in text.lower() for keyword in search_keywords) and not "для вакансии" in text.lower() and not "по вакансии" in text.lower():
        try:
            user_query = text.lower()

            position = None
            position_raw = None

            temp_query = user_query
            for cmd in search_keywords:
                temp_query = temp_query.replace(cmd, '')

            profession_keywords = [
                'инженер-конструктор', 'торговый представитель', 'аккаунт-менеджер',
                'офис-менеджер', 'smm-менеджер', 'hr-менеджер',
                'разработчик', 'программист', 'backend', 'frontend', 'devops',
                'инженер', 'конструктор', 'технолог', 'механик', 'электрик', 'сварщик',
                'строитель', 'архитектор', 'проектировщик', 'сметчик', 'геодезист',
                'логист', 'водитель', 'кладовщик', 'диспетчер',
                'менеджер', 'администратор', 'секретарь',
                'продавец',
                'маркетолог', 'копирайтер',
                'бухгалтер', 'финансист', 'экономист', 'аудитор',
                'рекрутер', 'кадровик'
            ]
            for prof in profession_keywords:
                if prof in user_query:
                    position = prof
                    position_raw = prof
                    break

            if position:
                position = re.sub(r'(а|у|я|е|ы|и|ой|ем|е)$', '', position.lower())
                logger.info(f"Должность после нормализации: '{position}'")


            text_for_skills = user_query
            if position:
                text_for_skills = text_for_skills.replace(position, '')
            if position_raw:
                text_for_skills = text_for_skills.replace(position_raw, '')
            for cmd in search_keywords:
                text_for_skills = text_for_skills.replace(cmd, '')

            words = re.findall(r'[a-zA-Zа-яА-Я0-9+#.]+', text_for_skills)
            stop_words = [
                "с", "со", "и", "или", "не", "на", "по", "за", "для", "кто", "что",
                "как", "где", "когда", "это", "тот", "эта", "этот", "свой", "свою",
                "кандидат", "кандидата", "кандидатов", "специалист", "специалиста",
                "человек", "человека", "навык", "навыками", "опыт", "опытом",
                "год", "года", "лет", "от"
            ]

            skills_list = []
            for word in words:
                if word not in stop_words and len(word) > 2:
                    if position and (word in position or position in word):
                        continue
                    skills_list.append(word)

            logger.info(f"Навыки: {skills_list}")

            experience_match = None
            exp_patterns = [
                r'опыт(?:ом)?\s*(\d+)',
                r'(\d+)\s*г(?:од|ода|од|\.)?',
                r'(\d+)\s*лет',
                r'с\s*опытом\s*(\d+)',
                r'(\d+)\s*год(?:а|ов)?'
            ]
            for pattern in exp_patterns:
                match = re.search(pattern, user_query)
                if match:
                    experience_match = int(match.group(1))
                    break

            logger.info(f"🔍 Поиск: должность='{position}', навыки={skills_list}, опыт={experience_match}")


            if not skills_list and experience_match is None and not position:
                all_candidates_for_list = HRAgentFacade.get_all_candidates_dict(limit=50)
                if all_candidates_for_list:
                    output = ["👥 **ВСЕ КАНДИДАТЫ В БАЗЕ:**", ""]
                    for i, cand in enumerate(all_candidates_for_list[:20], 1):
                        output.append(f"{i}. **{cand.get('name', 'Без имени')}**")
                        output.append(f"   • Опыт: {cand.get('experience_years', 0)} лет")
                        if cand.get('last_position'):
                            output.append(f"   • Должность: {cand.get('last_position')}")
                        output.append("")
                    if len(all_candidates_for_list) > 20:
                        output.append(f"... и ещё {len(all_candidates_for_list) - 20} кандидатов")
                    await update.message.reply_text("\n".join(output), reply_markup=get_main_keyboard())
                else:
                    await update.message.reply_text("📭 База кандидатов пуста", reply_markup=get_main_keyboard())
                return


            all_candidates = HRAgentFacade.search_candidates(
                skills=skills_list if skills_list else None,
                min_experience=experience_match,
                position=position,
                query_text=None,
                top_n=100
            )
            _remember_candidates_context(context, all_candidates)


            if all_candidates:
                output = ["🔍 **РЕЗУЛЬТАТЫ ПОИСКА**", ""]

                criteria = []
                if skills_list:
                    criteria.append(f"📌 Навыки: {', '.join(skills_list[:5])}")
                if experience_match:
                    criteria.append(f"📌 Опыт: от {experience_match} лет")
                if position:
                    criteria.append(f"📌 Должность: {position}")

                if criteria:
                    output.extend(criteria)
                    output.append("")

                for i, cand in enumerate(all_candidates[:20], 1):
                    match_percent = cand.get('match_percent', 0)

                    if match_percent >= 70:
                        emoji = "🏆"
                    elif match_percent >= 40:
                        emoji = "📊"
                    elif match_percent >= 20:
                        emoji = "🔍"
                    else:
                        emoji = "📄"

                    output.append(f"{emoji} **{i}. {cand.get('name', 'Без имени')}** — {match_percent}%")
                    output.append(f"   • Опыт: {cand.get('experience_years', 0)} лет")

                    if cand.get('last_position'):
                        output.append(f"   • Должность: {cand.get('last_position')}")
                    if cand.get('last_company'):
                        output.append(f"   • Компания: {cand.get('last_company')}")
                    if cand.get('skills'):
                        skills = cand.get('skills', [])[:5]
                        output.append(f"   • Навыки: {', '.join(skills)}")
                    output.append("")

                if len(all_candidates) > 20:
                    output.append(f"... и ещё {len(all_candidates) - 20} кандидатов")

                response_text = "\n".join(output)
                _save_dialog_turn(context, text, response_text, {"type": "candidate_search"})
                await update.message.reply_text(response_text, reply_markup=get_main_keyboard())
            else:
                all_candidates_manual = HRAgentFacade.get_all_candidates_dict(limit=100)
                found_manual = []

                for cand in all_candidates_manual:
                    cand_position = (cand.get('last_position') or "").lower()
                    if position and position.lower() in cand_position:
                        cand['match_percent'] = 50
                        found_manual.append(cand)

                if found_manual:
                    _remember_candidates_context(context, found_manual)
                    output = ["🔍 **РЕЗУЛЬТАТЫ ПОИСКА**", ""]
                    if position:
                        output.append(f"📌 Должность: {position}")
                        output.append("")

                    for i, cand in enumerate(found_manual[:20], 1):
                        output.append(f"📄 **{i}. {cand.get('name', 'Без имени')}**")
                        output.append(f"   • Опыт: {cand.get('experience_years', 0)} лет")
                        if cand.get('last_position'):
                            output.append(f"   • Должность: {cand.get('last_position')}")
                        if cand.get('last_company'):
                            output.append(f"   • Компания: {cand.get('last_company')}")
                        output.append("")

                    response_text = "\n".join(output)
                    _save_dialog_turn(context, text, response_text, {"type": "candidate_search"})
                    await update.message.reply_text(response_text, reply_markup=get_main_keyboard())
                else:
                    await update.message.reply_text(
                        f"😕 Кандидаты не найдены по запросу: {text}\n\n"
                        f"💡 **Попробуйте:**\n"
                        f"   • 'найди python разработчика'\n"
                        f"   • 'ищу frontend специалиста с опытом 3 года'\n"
                        f"   • 'покажи кандидатов из Яндекса'\n"
                        f"   • 'найди бухгалтера с опытом 5 лет'\n"
                        f"   • 'найди инженера-конструктора'\n\n"
                        f"📋 Или посмотрите всех: 'покажи кандидатов'",
                        reply_markup=get_main_keyboard()
                    )

        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(
                f"😕 Ошибка поиска. Попробуйте позже.\n\n"
                f"Альтернатива: используйте кнопку '👥 Показать всех кандидатов'",
                reply_markup=get_main_keyboard()
            )
        return


    if text == "📋 Все опросы":
        await show_surveys_list(update, context=context)
        return

    if text == "📊 Создать NPS опрос":
        title = f"NPS опрос от {datetime.now().strftime('%d.%m.%Y')}"
        survey_id = HRAgentFacade.create_survey(title, "nps", None)
        bot_username = (await context.bot.get_me()).username
        survey_link = f"https://t.me/{bot_username}?start=survey_{survey_id}"
        await update.message.reply_text(
            f"✅ **NPS ОПРОС СОЗДАН!**\n\n• ID: {survey_id}\n• Название: {title}\n\n🔗 **Ссылка:**\n{survey_link}",
            reply_markup=get_surveys_keyboard()
        )
        return

    if text == "💓 Создать Pulse опрос":
        title = f"Pulse опрос от {datetime.now().strftime('%d.%m.%Y')}"
        survey_id = HRAgentFacade.create_survey(title, "pulse", None)
        bot_username = (await context.bot.get_me()).username
        survey_link = f"https://t.me/{bot_username}?start=survey_{survey_id}"
        await update.message.reply_text(
            f"✅ **PULSE ОПРОС СОЗДАН!**\n\n• ID: {survey_id}\n• Название: {title}\n\n🔗 **Ссылка:**\n{survey_link}",
            reply_markup=get_surveys_keyboard()
        )
        return


    if any(trigger in text.lower() for trigger in SURVEY_ANALYZE_TRIGGERS):
        await analyze_survey_command(update, text)
        return


    if any(trigger in text.lower() for trigger in SURVEY_DELETE_ALL_TRIGGERS):
        context.user_data["user_state"] = {"state": "confirm_delete_all_surveys"}
        await update.message.reply_text(
            "⚠️ **ВНИМАНИЕ!**\n\n"
            "Вы действительно хотите удалить ВСЕ опросы и все ответы?\n\n"
            "Это действие нельзя отменить.\n\n"
            "Напишите **ДА** для подтверждения или **отмена** для отмены.",
            reply_markup=get_cancel_keyboard()
        )
        return

    if any(trigger in text.lower() for trigger in SURVEY_DELETE_TRIGGERS) and "все" not in text.lower():
        await delete_survey_command(update, text)
        return


    if any(trigger in text.lower() for trigger in SURVEY_LIST_TRIGGERS):
        await show_surveys_list(update)
        return


    if any(trigger in text.lower() for trigger in CHART_TRIGGERS):
        await chart_command(update, text)
        return


    if any(trigger in text.lower() for trigger in SURVEY_NPS_CHART_TRIGGERS):
        await nps_chart_command(update, text)
        return


    if any(trigger in text.lower() for trigger in SURVEY_PULSE_CHART_TRIGGERS):
        await pulse_chart_command(update, text)
        return


    if any(trigger in text.lower() for trigger in JOB_ARCHIVE_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            job = HRAgentFacade.get_job(job_id)
            if not job:
                await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
                return
            if job.get('status') == 'archived':
                await update.message.reply_text(f"📦 Вакансия уже в архиве")
                return
            if HRAgentFacade.archive_job(job_id):
                await update.message.reply_text(f"✅ Вакансия **{job.get('title')}** отправлена в архив", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("❌ Не удалось архивировать")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'архивировать вакансию 1'")
        return

    if any(trigger in text.lower() for trigger in JOB_ACTIVATE_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            job = HRAgentFacade.get_job(job_id)
            if not job:
                await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
                return
            if job.get('status') == 'active':
                await update.message.reply_text(f"✅ Вакансия уже активна")
                return
            if HRAgentFacade.activate_job(job_id):
                await update.message.reply_text(f"✅ Вакансия **{job.get('title')}** активирована", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("❌ Не удалось активировать")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'активировать вакансию 1'")
        return


    if any(trigger in text.lower() for trigger in CANDIDATE_RESTORE_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            if HRAgentFacade.restore_candidate(candidate_id):
                await update.message.reply_text(f"✅ Кандидат ID {candidate_id} восстановлен из корзины", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден в корзине", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'восстановить кандидата 1'", reply_markup=get_cancel_keyboard())
        return


    if re.search(r'удалить\s+всех\s+кандидатов\s+из\s+архива', text.lower()):
        archived_count = len(HRAgentFacade.get_archived_candidates(limit=10000))
        if archived_count == 0:
            await update.message.reply_text("📭 Архив кандидатов уже пуст", reply_markup=get_main_keyboard())
            return

        context.user_data["user_state"] = {
            "state": "confirm_delete_all_archived_candidates",
            "count": archived_count,
        }
        await update.message.reply_text(
            "⚠️ **ВНИМАНИЕ!**\n\n"
            f"Вы действительно хотите НАВСЕГДА удалить всех кандидатов из архива?\n"
            f"Будет удалено записей: **{archived_count}**\n\n"
            "Это действие нельзя отменить.\n\n"
            "Напишите **ДА** для подтверждения или **отмена** для отмены.",
            reply_markup=get_cancel_keyboard()
        )
        return

    match_delete_archived = re.search(r'удалить\s+кандидата\s+(\d+)\s+из\s+архива', text.lower())
    if match_delete_archived:
        candidate_id = int(match_delete_archived.group(1))
        if not HRAgentFacade.is_candidate_archived(candidate_id):
            await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден в архиве")
            return

        archived_list = HRAgentFacade.get_archived_candidates(limit=10000)
        candidate_name = "Без имени"
        for cand in archived_list:
            if cand.get("id") == candidate_id:
                candidate_name = cand.get("name", "Без имени")
                break

        context.user_data["user_state"] = {
            "state": "confirm_delete_archived_candidate",
            "candidate_id": candidate_id,
            "name": candidate_name,
        }
        await update.message.reply_text(
            f"⚠️ Вы уверены, что хотите НАВСЕГДА удалить из архива кандидата "
            f"**{candidate_name}** (ID: {candidate_id})?\n\n"
            "Это действие нельзя отменить.\n\n"
            "Напишите **ДА** для подтверждения или **отмена** для отмены.",
            reply_markup=get_cancel_keyboard()
        )
        return


    if any(trigger in text.lower() for trigger in ["архивировать кандидата", "в архив", "отказ"]):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
                return

            reason = "manual"
            if "отказ" in text.lower():
                reason = "rejected"
            elif "нанят" in text.lower():
                reason = "hired"

            if HRAgentFacade.archive_candidate(candidate_id, reason):
                reason_text = "отказ" if reason == "rejected" else "найм" if reason == "hired" else "архивацию"
                await update.message.reply_text(
                    f"✅ Кандидат **{candidate.get('name', 'Без имени')}** (ID: {candidate_id}) отправлен в архив.\n"
                    f"📌 Причина: {reason_text}",
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(f"❌ Не удалось архивировать кандидата")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'архивировать кандидата 1'")
        return

    if any(trigger in text.lower() for trigger in ["показать архив", "архив", "архивированные", "список архива"]):
        archived = HRAgentFacade.get_archived_candidates(limit=50)
        if not archived:
            await update.message.reply_text("📭 Архив пуст", reply_markup=get_main_keyboard())
            return

        output = ["📦 **АРХИВ КАНДИДАТОВ**", ""]
        for cand in archived[:20]:
            reason_text = {
                "hired": "✅ Нанят",
                "rejected": "❌ Отказ",
                "manual": "📦 В архиве"
            }.get(cand.get('archive_reason'), "📦 В архиве")

            archived_at = cand.get('archived_at')
            if archived_at:
                if hasattr(archived_at, 'strftime'):
                    archived_at_str = archived_at.strftime('%Y-%m-%d %H:%M')
                else:
                    archived_at_str = str(archived_at)[:16]
            else:
                archived_at_str = '—'

            output.append(f"**#{cand.get('id')}** — {cand.get('name', 'Без имени')}")
            output.append(f"   • {reason_text}")
            if cand.get('last_position'):
                output.append(f"   • {cand.get('last_position')}")
            output.append(f"   • Архивирован: {archived_at_str}")
            output.append("")

        if len(archived) > 20:
            output.append(f"... и ещё {len(archived) - 20} кандидатов")

        output.append("\n💡 Чтобы восстановить: `восстановить из архива ID`")
        await update.message.reply_text("\n".join(output), reply_markup=get_main_keyboard())
        return

    if any(trigger in text.lower() for trigger in ["вернуть из архива", "восстановить из архива кандидата"]):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            if not HRAgentFacade.is_candidate_archived(candidate_id):
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден в архиве")
                return

            archived_list = HRAgentFacade.get_archived_candidates(limit=100)
            candidate_name = "кандидата"
            for cand in archived_list:
                if cand.get('id') == candidate_id:
                    candidate_name = cand.get('name', 'кандидата')
                    break

            if HRAgentFacade.restore_from_archive(candidate_id):
                await update.message.reply_text(
                    f"✅ Кандидат **{candidate_name}** (ID: {candidate_id}) восстановлен из архива",
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(f"❌ Не удалось восстановить кандидата")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'вернуть из архива 1'")
        return

    state_obj = context.user_data.get("user_state", {})
        
    if isinstance(state_obj, dict) and state_obj:
        if state_obj.get("state") == "onboarding_waiting_for_name":
            await handle_onboarding_start(update, candidate_name=text, context=context)
            return
        if state_obj.get("state") == "onboarding_waiting_for_role":
            await handle_onboarding_role(update, text, state_obj.get("name"), context=context)
            return
        if state_obj.get("state") == "onboarding_waiting_for_level":
            await handle_onboarding_level(update, text, state_obj.get("name"), state_obj.get("department"), state_obj.get("role_text"), state_obj.get("dept_name"), context=context)
            return
        if state_obj.get("state") == "onboarding_waiting_for_date":
            await handle_onboarding_date(update, text, state_obj.get("name"), state_obj.get("department", "development"), state_obj.get("level"), state_obj.get("role_text", "Сотрудник"), state_obj.get("dept_name", "Разработка"), context=context)
            return

        if state_obj.get("state") == "waiting_for_name":
            await handle_candidate_addition(user_id, text, update, context=context)
            return
        if state_obj.get("state") == "waiting_for_email":
            await handle_candidate_addition(user_id, text, update, context=context)
            return
        if state_obj.get("state") == "waiting_for_phone":
            await handle_candidate_addition(user_id, text, update, context=context)
            return
        if state_obj.get("state") == "waiting_for_experience":
            await handle_candidate_addition(user_id, text, update, context=context)
            return
        if state_obj.get("state") == "waiting_for_position":
            await handle_candidate_addition(user_id, text, update, context=context)
            return
        if state_obj.get("state") == "waiting_for_company":
            await handle_candidate_addition(user_id, text, update, context=context)
            return
        if state_obj.get("state") == "waiting_for_skills":
            await handle_candidate_addition(user_id, text, update, context=context)
            return

        if state_obj.get("state") == "test_waiting_for_direction":
            from .utils import detect_direction_from_role
            direction = detect_direction_from_role(text)
            if direction:
                status_msg = await update.message.reply_text(
                    f"🔄 **Генерация тестового задания**\n\n"
                    f"🎯 Направление: {DIRECTION_NAMES.get(direction, direction)}\n\n"
                    f"⏳ Пожалуйста, подождите..."
                )
                from app.services.test_generator import generate_test, format_test
                test = generate_test(
                    direction=direction,
                    level="middle",
                    tech_stack=state_obj.get("tech_stack", []),
                    candidate_name=state_obj.get("candidate_name")
                )
                await status_msg.delete()

                if "error" in test:
                    await update.message.reply_text(f"❌ Ошибка: {test['error']}", reply_markup=get_main_keyboard())
                else:
                    temp_data_local = context.user_data.get("temp_data", {})
                    temp_data_local["last_test"] = test
                    context.user_data["temp_data"] = temp_data_local
                    formatted = format_test(test)
                    formatted += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    formatted += "\n📌 **Чтобы сохранить тест в PDF, напишите:**"
                    formatted += "\n   • `экспорт теста в pdf`"
                    formatted += "\n   • `сохранить тест в pdf имя_файла.pdf`"
                    formatted += "\n\n✏️ **Чтобы отредактировать тест, напишите:**"
                    formatted += "\n   • `редактировать тест`"
                    formatted += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    await update.message.reply_text(formatted, parse_mode="Markdown", reply_markup=get_main_keyboard())

                context.user_data["user_state"] = {}
            else:
                await update.message.reply_text(
                    "❌ Не удалось определить направление.\n"
                    "Напишите: it, production, construction, logistics, office, sales, marketing, finance, hr\n"
                    "Или: frontend, backend, fullstack, devops, mobile",
                    reply_markup=get_cancel_keyboard()
                )
            return

        if state_obj.get("state") == "test_waiting_for_level":
            level = text.lower()
            if level not in ["junior", "middle", "senior"]:
                await update.message.reply_text("❌ Неверный уровень. Напишите: junior, middle или senior")
                return

            status_msg = await update.message.reply_text("🔄 Генерация...")
            from app.services.test_generator import generate_test, format_test
            test = generate_test(
                direction=state_obj.get("direction"), level=level,
                tech_stack=state_obj.get("tech_stack", []),
                candidate_name=state_obj.get("candidate_name")
            )
            await status_msg.delete()

            if "error" in test:
                await update.message.reply_text(f"❌ Ошибка: {test['error']}")
            else:
                temp_data_local = context.user_data.get("temp_data", {})
                temp_data_local["last_test"] = test
                context.user_data["temp_data"] = temp_data_local
                formatted = format_test(test)
                formatted += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                formatted += "\n📌 **Чтобы сохранить тест в PDF, напишите:**"
                formatted += "\n   • `экспорт теста в pdf`"
                formatted += "\n   • `сохранить тест в pdf имя_файла.pdf`"
                formatted += "\n\n✏️ **Чтобы отредактировать тест, напишите:**"
                formatted += "\n   • `редактировать тест`"
                formatted += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                await update.message.reply_text(formatted, parse_mode="Markdown", reply_markup=get_main_keyboard())

            context.user_data["user_state"] = {}
            return

        if state_obj.get("state") == "editing_test":
            await handle_editing_test(update, text, user_id, state_obj)
            return

        if state_obj.get("state") == "editing_onboarding":
            await handle_editing_onboarding(update, text, user_id, state_obj)
            return

        if state_obj.get("state") == "survey_waiting_for_score":
            survey_id = state_obj.get("survey_id")
            survey = HRAgentFacade.get_survey(survey_id)
            survey_type = survey.get("type", "nps") if survey else "nps"

            try:
                score = int(text)
                if survey_type == "nps":
                    if 0 <= score <= 10:
                        context.user_data["user_state"] = {
                            "state": "survey_waiting_for_feedback",
                            "survey_id": survey_id,
                            "score": score,
                            "survey_type": survey_type
                        }
                        await update.message.reply_text(
                            f"✅ Оценка: {score}\n\nВопрос 2: Что можно улучшить?\nНапишите ваш отзыв:",
                            reply_markup=get_cancel_keyboard()
                        )
                    else:
                        await update.message.reply_text("❌ Оценка должна быть от 0 до 10")
                else:
                    if 1 <= score <= 5:
                        context.user_data["user_state"] = {
                            "state": "survey_waiting_for_energy",
                            "survey_id": survey_id,
                            "satisfaction": score,
                            "survey_type": survey_type
                        }
                        await update.message.reply_text(
                            f"✅ Удовлетворённость: {score}\n\nВопрос 2: Уровень энергии?\nОцените от 1 до 5:",
                            reply_markup=get_cancel_keyboard()
                        )
                    else:
                        await update.message.reply_text("❌ Оценка должна быть от 1 до 5")
            except ValueError:
                await update.message.reply_text("❌ Введите число")
            return

        if state_obj.get("state") == "survey_waiting_for_energy":
            try:
                energy = int(text)
                if 1 <= energy <= 5:
                    context.user_data["user_state"] = {
                        "state": "survey_waiting_for_feedback",
                        "survey_id": state_obj.get("survey_id"),
                        "survey_type": state_obj.get("survey_type"),
                        "satisfaction": state_obj.get("satisfaction"),
                        "energy": energy,
                        "answers": {"satisfaction": state_obj.get("satisfaction"), "energy": energy}
                    }
                    await update.message.reply_text(
                        f"✅ Уровень энергии: {energy}\n\nВопрос 3: Ваш фидбек?\nНапишите ваш отзыв:",
                        reply_markup=get_cancel_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ Оценка должна быть от 1 до 5")
            except ValueError:
                await update.message.reply_text("❌ Введите число")
            return

        if state_obj.get("state") == "survey_waiting_for_feedback":
            survey_id = state_obj.get("survey_id")
            survey_type = state_obj.get("survey_type", "nps")
            feedback = text

            if survey_type == "nps":
                answers = {"nps_score": state_obj.get("score")}
            else:
                answers = state_obj.get("answers", {})

            HRAgentFacade.submit_survey_response(
                survey_id=survey_id, answers=answers,
                respondent_name=update.effective_user.first_name,
                feedback=feedback
            )

            await update.message.reply_text("✅ **Спасибо за участие в опросе!**", reply_markup=get_main_keyboard())
            context.user_data["user_state"] = {}
            return

        if state_obj.get("state") == "confirm_delete_all_surveys":
            await confirm_delete_all_surveys(update, text, user_id, context=context)
            return
        if state_obj.get("state") == "confirm_delete_all_candidates":
            await confirm_delete_all_candidates(update, text, user_id, context=context)
            return
        if state_obj.get("state") == "confirm_delete_all_jobs":
            await confirm_delete_all_jobs(update, text, user_id, context=context)
            return
        if state_obj.get("state") == "confirm_delete_candidate":
            await confirm_delete_candidate(update, text, user_id, state_obj, context=context)
            return
        if state_obj.get("state") == "confirm_delete_archived_candidate":
            if text.strip().upper() == "ДА":
                candidate_id = state_obj.get("candidate_id")
                name = state_obj.get("name", "Без имени")
                if HRAgentFacade.delete_archived_candidate(candidate_id):
                    await update.message.reply_text(
                        f"✅ Кандидат **{name}** (ID: {candidate_id}) навсегда удалён из архива",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Кандидат с ID {candidate_id} не найден в архиве",
                        reply_markup=get_main_keyboard()
                    )
                context.user_data["user_state"] = {}
            elif text.lower() in CANCEL_WORDS:
                context.user_data["user_state"] = {}
                await update.message.reply_text("✅ Удаление из архива отменено", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("Напишите **ДА** для подтверждения или **отмена** для отмены.")
            return
        if state_obj.get("state") == "confirm_delete_all_archived_candidates":
            if text.strip().upper() == "ДА":
                deleted_count = HRAgentFacade.delete_all_archived_candidates()
                context.user_data["user_state"] = {}
                await update.message.reply_text(
                    f"✅ Архив кандидатов очищен. Удалено записей: **{deleted_count}**",
                    reply_markup=get_main_keyboard()
                )
            elif text.lower() in CANCEL_WORDS:
                context.user_data["user_state"] = {}
                await update.message.reply_text("✅ Очистка архива отменена", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("Напишите **ДА** для подтверждения или **отмена** для отмены.")
            return

    state_str = context.user_data.get("user_state")
    if isinstance(state_str, str):
        if state_str == "job_waiting_for_title":
            await handle_job_addition(user_id, text, update, context=context)
            return
        if state_str == "job_waiting_for_level":
            await handle_job_addition(user_id, text, update, context=context)
            return
        if state_str == "job_waiting_for_skills":
            await handle_job_addition(user_id, text, update, context=context)
            return
        if state_str == "job_waiting_for_experience":
            await handle_job_addition(user_id, text, update, context=context)
            return
        if state_str == "job_waiting_for_description":
            await handle_job_addition(user_id, text, update, context=context)
            return
        
        if state_str == "editing_candidate":
            await handle_editing_candidate(update, text, user_id, state_str, context=context)
            return
        if state_str == "editing_job":
            await handle_editing_job(update, text, user_id, state_str, context=context)
            return
        
        if state_str in ["waiting_for_name", "waiting_for_email", "waiting_for_phone",
                         "waiting_for_experience", "waiting_for_position",
                         "waiting_for_company", "waiting_for_skills"]:
            await handle_candidate_addition(user_id, text, update, context=context)
            return
            

    if text.lower() in CANDIDATE_ADD_WORDS:
        context.user_data["user_state"] = "waiting_for_name"
        await update.message.reply_text(
            "📝 **Добавление кандидата**\n\nВведите **ФИО**:",
            reply_markup=get_cancel_keyboard()
        )
        return

    if text.lower() in JOB_ADD_WORDS:
        context.user_data["user_state"] = "job_waiting_for_title"
        context.user_data["temp_data"] = {}
        await update.message.reply_text(
            "💼 **Добавление вакансии**\n\nВведите **название**:",
            reply_markup=get_cancel_keyboard()
        )
        return

    if any(trigger in text.lower() for trigger in ONBOARDING_TRIGGERS):
        await handle_onboarding_start(update, context=context)
        return

    if any(trigger in text.lower() for trigger in TEST_TRIGGERS):
        if any(word in text.lower() for word in ["этой вакансии", "эта вакансия", "текущей вакансии", "последней вакансии"]):
            if await _generate_test_for_last_job(update, context):
                return
        await handle_test_generation(update, text)
        return

    if any(trigger in text.lower() for trigger in SURVEY_CREATE_TRIGGERS):
        await create_survey_command(update, context, text)
        return

    if any(trigger in text.lower() for trigger in CANDIDATE_DELETE_ALL_TRIGGERS):
        context.user_data["user_state"] = {"state": "confirm_delete_all_candidates"}
        await update.message.reply_text(
            "⚠️ **ВНИМАНИЕ!**\n\n"
            "Вы действительно хотите удалить ВСЕХ кандидатов?\n\n"
            "Это действие нельзя отменить.\n\n"
            "Напишите **ДА** для подтверждения или **отмена** для отмены.",
            reply_markup=get_cancel_keyboard()
        )
        return

    if any(trigger in text.lower() for trigger in JOB_DELETE_ALL_TRIGGERS):
        context.user_data["user_state"] = {"state": "confirm_delete_all_jobs"}
        await update.message.reply_text(
            "⚠️ **ВНИМАНИЕ!**\n\n"
            "Вы действительно хотите удалить ВСЕ вакансии?\n\n"
            "Это действие нельзя отменить.\n\n"
            "Напишите **ДА** для подтверждения или **отмена** для отмены.",
            reply_markup=get_cancel_keyboard()
        )
        return

    if any(trigger in text.lower() for trigger in CANDIDATE_EDIT_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
                return
            context.user_data["temp_data"] = {"edit_candidate_id": candidate_id, "edit_step": "name"}
            context.user_data["user_state"] = "editing_candidate"
            await update.message.reply_text(
                f"✏️ **Редактирование кандидата #{candidate_id}**\n\n"
                f"Текущее имя: {candidate.get('name', '—')}\n\n"
                f"Введите **новое имя** (или '-' чтобы пропустить, 'отмена' для отмены)",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'редактировать кандидата 1'")
        return

    if any(trigger in text.lower() for trigger in JOB_EDIT_TRIGGERS):
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            job = HRAgentFacade.get_job(job_id)
            if not job:
                await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
                return
            context.user_data["temp_data"] = {"edit_job_id": job_id, "edit_step": "title"}
            context.user_data["user_state"] = "editing_job"
            await update.message.reply_text(
                f"✏️ **Редактирование вакансии #{job_id}**\n\n"
                f"Текущее название: {job.get('title', '—')}\n\n"
                f"Введите **новое название** (или '-' чтобы пропустить, 'отмена' для отмены)",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'редактировать вакансию 1'")
        return


    if any(trigger in text.lower() for trigger in CANDIDATE_INFO_TRIGGERS):
        await show_candidate_info(update, text)
        return


    if text.lower().startswith("кандидат "):
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if candidate:
                _remember_candidate_context(context, candidate)
                output = [
                    f"👤 **{candidate.get('name', 'Без имени')}**",
                    f"📧 Email: {candidate.get('email', '—')}",
                    f"📞 Телефон: {candidate.get('phone', '—')}",
                    f"💼 Опыт: {format_years(candidate.get('experience_years', 0))}",
                    f"📋 Последняя должность: {candidate.get('last_position', '—')}",
                    f"🏢 Последняя компания: {candidate.get('last_company', '—')}",
                    f"🛠️ Навыки: {', '.join(candidate.get('skills', []))}",
                    f"📅 Создан: {candidate.get('created_at', '—')}",
                ]
                response_text = "\n".join(output)
                _save_dialog_turn(context, text, response_text, {"type": "job_info", "job_id": job_id})
                await update.message.reply_text(response_text, reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'кандидат 29'")
        return


    if any(trigger in text.lower() for trigger in JOB_INFO_TRIGGERS):
        await show_job_info(update, text)
        return


    if any(trigger in text.lower() for trigger in JOB_LIST_TRIGGERS):
        await show_jobs_list(update, context=context)
        return


    if text.lower().startswith("вакансия "):
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            job = HRAgentFacade.get_job(job_id)
            if job:
                _remember_job_context(context, job)
                status_icon = "✅" if job.get('status') == 'active' else "📦"
                level_icon = "🟢" if job.get('level') == 'junior' else "🟡" if job.get('level') == 'middle' else "🔴"
                output = [
                    f"💼 **{job.get('title', '—')}**",
                    f"📊 Уровень: {job.get('level', '—')}",
                    f"💼 Требуемый опыт: {job.get('experience', 0)} лет",
                    f"🛠️ Навыки: {', '.join(job.get('skills', []))}",
                    f"📝 Описание: {job.get('description', '—')}",
                    f"📅 Создана: {job.get('created_at', '—')}",
                    f"📌 Статус: {status_icon} {job.get('status', '—')}",
                ]
                await update.message.reply_text("\n".join(output), reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'вакансия 1'")
        return


    if any(trigger in text.lower() for trigger in CANDIDATE_LIST_TRIGGERS):
        await show_candidates_list(update)
        return


    if any(trigger in text.lower() for trigger in CANDIDATE_DELETE_TRIGGERS) and "всех" not in text.lower():
        numbers = re.findall(r'\d+', text)
        if numbers:
            candidate_id = int(numbers[0])
            candidate = HRAgentFacade.get_candidate(candidate_id)
            if not candidate:
                await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
                return
            name = candidate.get('name', 'Без имени')
            context.user_data["user_state"] = {"state": "confirm_delete_candidate", "candidate_id": candidate_id, "name": name}
            await update.message.reply_text(
                f"⚠️ Вы уверены, что хотите удалить кандидата **{name}** (ID: {candidate_id})?\n\n"
                f"Напишите **ДА** для подтверждения или **отмена** для отмены.",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'удалить кандидата 2'")
        return


    if any(trigger in text.lower() for trigger in JOB_DELETE_TRIGGERS) and "всех" not in text.lower():
        numbers = re.findall(r'\d+', text)
        if numbers:
            job_id = int(numbers[0])
            job = HRAgentFacade.get_job(job_id)
            if not job:
                await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
                return
            title = job.get('title', 'Без названия')
            if HRAgentFacade.delete_job(job_id):
                await update.message.reply_text(f"✅ Вакансия **{title}** удалена", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text(f"❌ Не удалось удалить")
        else:
            await update.message.reply_text("❌ Укажите ID. Пример: 'удалить вакансию 2'")
        return


    if any(trigger in text.lower() for trigger in STATISTICS_TRIGGERS):
        candidates = HRAgentFacade.get_all_candidates(limit=1000)
        jobs = HRAgentFacade.get_all_jobs(active_only=False)
        await update.message.reply_text(
            f"📊 **СТАТИСТИКА**\n\n👥 Кандидатов: {len(candidates)}\n💼 Вакансий: {len(jobs)}",
            reply_markup=get_main_keyboard()
        )
        return


    if any(trigger in text.lower() for trigger in CANDIDATE_EXPORT_EXCEL_TRIGGERS):
        from app.utils.excel_export import export_candidates_to_excel
        candidates = HRAgentFacade.get_all_candidates(limit=10000)
        if not candidates:
            await update.message.reply_text("📭 Нет кандидатов для экспорта")
            return
        filepath = export_candidates_to_excel(candidates)
        with open(filepath, 'rb') as f:
            await update.message.reply_document(document=f, filename=Path(filepath).name, caption=f"✅ Экспортировано {len(candidates)} кандидатов")
        Path(filepath).unlink()
        return


    if _is_parsing_command(text, PARSING_NO_WORDS):
        if context.user_data.get("temp_data", {}).get("parsed_candidate"):
            _cleanup_temp_file(context.user_data.get("temp_data", {}).get("file_path"))
            context.user_data["temp_data"] = {}
            await update.message.reply_text("✅ Отменено. Данные кандидата не сохранены.", reply_markup=get_main_keyboard())
        return

    if _is_parsing_command(text, PARSING_YES_WORDS):
        if context.user_data.get("temp_data", {}).get("parsed_candidate"):
            candidate_data = context.user_data["temp_data"]["parsed_candidate"]
            file_path = context.user_data["temp_data"].get("file_path")
            try:
                candidate_id = HRAgentFacade.save_candidate(candidate_data, file_path)
                await update.message.reply_text(f"✅ Кандидат добавлен! ID: {candidate_id}", reply_markup=get_main_keyboard())
                _cleanup_temp_file(file_path)
                context.user_data["temp_data"] = {}
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {str(e)}")
                return
        else:
            await update.message.reply_text("❌ Нет данных для сохранения. Сначала отправьте резюме")
        return

    if _is_parsing_command(text, PARSING_UPDATE_WORDS):
        if context.user_data.get("temp_data", {}).get("parsed_candidate"):
            candidate_data = context.user_data["temp_data"]["parsed_candidate"]
            file_path = context.user_data["temp_data"].get("file_path")
            try:
                candidate_id = HRAgentFacade.save_candidate(candidate_data, file_path)
                await update.message.reply_text(f"✅ Кандидат обновлён! ID: {candidate_id}", reply_markup=get_main_keyboard())
                _cleanup_temp_file(file_path)
                context.user_data["temp_data"] = {}
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {str(e)}")
                return
        else:
            await update.message.reply_text("❌ Нет данных для обновления")
        return


    try:
        await update.message.chat.send_action(action="typing")
        status_msg = await update.message.reply_text("🤔 Обрабатываю запрос...")

        response = await _chat_with_hr_agent(context, text)
        await status_msg.delete()
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при вызове LLM: {e}")
        await update.message.reply_text("😕 Ошибка при обработке запроса. Попробуйте ещё раз.")
