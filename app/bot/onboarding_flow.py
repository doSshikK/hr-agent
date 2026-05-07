"""
app/bot/onboarding_flow.py
Пошаговый интерактивный онбординг для нового сотрудника
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logger import get_logger
from app.services.hr_facade import HRAgentFacade
from app.services.onboarding_generator import format_onboarding_plan
from app.utils.reminder import reminder_service, schedule_onboarding_reminders, cancel_onboarding_reminders
from app.bot.onboarding_interactive import find_answer_by_keywords, get_quick_answers

logger = get_logger(__name__)


def get_onboarding_main_keyboard() -> InlineKeyboardMarkup:
    """Старая inline-клавиатура. Оставлена для совместимости со старыми сообщениями."""
    keyboard = [
        [
            InlineKeyboardButton("📋 Мои задачи", callback_data="onb_tasks"),
            InlineKeyboardButton("📅 Мои встречи", callback_data="onb_meetings"),
        ],
        [
            InlineKeyboardButton("❓ Задать вопрос", callback_data="onb_help"),
            InlineKeyboardButton("📊 Мой прогресс", callback_data="onb_progress"),
        ],
        [
            InlineKeyboardButton("🏠 В главное меню", callback_data="onb_exit"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_onboarding_reply_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура кандидата в режиме онбординга."""
    keyboard = [
        [KeyboardButton("✅ Текущая задача")],
        [KeyboardButton("✅ Выполнить текущую")],
        [KeyboardButton("❓ Помощь по задаче")],
        [KeyboardButton("📋 Все задачи"), KeyboardButton("👥 Все встречи")],
        [KeyboardButton("📊 Прогресс"), KeyboardButton("❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_task_navigation_keyboard(current_task: int, total_tasks: int, task_text: str = "") -> InlineKeyboardMarkup:
    """Клавиатура для навигации по задачам"""
    keyboard = []
    
    nav_row = []
    if current_task > 1:
        nav_row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"onb_task_prev_{current_task}"))
    if current_task < total_tasks:
        nav_row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"onb_task_next_{current_task}"))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([
        InlineKeyboardButton("✅ Отметить готовым", callback_data=f"onb_complete_{current_task}"),
        InlineKeyboardButton("❓ Как сделать?", callback_data=f"onb_howto_{current_task}"),
    ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад в меню", callback_data="onb_back_to_menu"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_meetings_keyboard(meetings: list, current_index: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра встреч"""
    keyboard = []
    
    if len(meetings) > 1:
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"onb_meeting_prev_{current_index}"))
        if current_index < len(meetings) - 1:
            nav_row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"onb_meeting_next_{current_index}"))
        if nav_row:
            keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="onb_back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_faq_topics_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с быстрыми темами базы знаний новичка."""
    topics = list(get_quick_answers().keys())
    keyboard = []
    row = []

    for index, topic in enumerate(topics):
        row.append(InlineKeyboardButton(topic.capitalize(), callback_data=f"onb_faq_{index}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="onb_back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_onboarding_session(context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
    """Возвращает активную сессию онбординга из context.user_data"""
    if context and hasattr(context, 'user_data'):
        return context.user_data.get("onboarding_session")
    return None


def set_onboarding_session(context: ContextTypes.DEFAULT_TYPE, plan: Dict[str, Any], step: int = 0, candidate_id: int = None):
    """Устанавливает сессию онбординга в context.user_data"""
    if context and hasattr(context, 'user_data'):
        context.user_data["onboarding_session"] = {
            "plan": plan,
            "step": step,
            "started_at": datetime.now().isoformat(),
            "completed_tasks": plan.get("completed_tasks", []),
            "current_meeting": 0,
            "candidate_id": candidate_id
        }


def clear_onboarding_session(context: ContextTypes.DEFAULT_TYPE):
    """Очищает сессию онбординга в context.user_data"""
    if context and hasattr(context, 'user_data'):
        if "onboarding_session" in context.user_data:
            del context.user_data["onboarding_session"]


def update_onboarding_step(context: ContextTypes.DEFAULT_TYPE, step: int):
    """Обновляет текущий шаг онбординга"""
    if context and hasattr(context, 'user_data'):
        session = context.user_data.get("onboarding_session")
        if session:
            session["step"] = step
            context.user_data["onboarding_session"] = session


def mark_task_completed(context: ContextTypes.DEFAULT_TYPE, task_index: int, task_text: str):
    """Отмечает задачу как выполненную"""
    if context and hasattr(context, 'user_data'):
        session = context.user_data.get("onboarding_session")
        if session:
            completed = session.get("completed_tasks", [])
            completed.append({
                "index": task_index,
                "task": task_text,
                "completed_at": datetime.now().isoformat()
            })
            session["completed_tasks"] = completed
            session["step"] = task_index + 1
            context.user_data["onboarding_session"] = session
            
            candidate_id = session.get("candidate_id")
            if candidate_id:
                HRAgentFacade.save_onboarding_progress(candidate_id, task_index + 1, completed)
                logger.info(f"💾 Прогресс онбординга сохранён в БД для кандидата {candidate_id}, шаг {task_index + 1}")


def get_progress_percent(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    """Возвращает процент выполнения и прогресс-бар"""
    session = get_onboarding_session(context)
    if not session:
        return 0, "░░░░░░░░░░"
    
    plan = session.get("plan", {})
    checklist = plan.get("checklist", [])
    completed_count = session.get("step", 0)
    total_count = len(checklist)
    
    if total_count == 0:
        return 0, "░░░░░░░░░░"
    
    percent = int(completed_count / total_count * 100)
    filled = percent // 10
    progress_bar = "█" * filled + "░" * (10 - filled)
    
    return percent, progress_bar


async def send_onboarding_plan(update: Update, context: ContextTypes.DEFAULT_TYPE, plan: Dict[str, Any], candidate_id: int = None):
    """Отправляет план онбординга пользователю и запускает интерактивную сессию (через update)"""
    user_id = update.effective_user.id
    bot = Bot(token=settings.telegram_bot_token)
    
    set_onboarding_session(context, plan, 0, candidate_id)
    
    if candidate_id:
        HRAgentFacade.start_onboarding(candidate_id)
        HRAgentFacade.save_onboarding_progress(candidate_id, 0, [])
    
    output = (
        "📋 **Онбординг открыт**\n\n"
        f"Дата начала: {plan.get('start_date_readable', '—')}\n"
        f"Задач: {len(plan.get('checklist', []))}\n"
        f"Встреч: {len(plan.get('meetings', []))}\n\n"
        "Я буду вести вас по шагам. В меню ниже можно открыть текущую задачу, "
        "посмотреть все задачи, встречи, прогресс или попросить помощь."
    )
    
    await bot.send_message(
        chat_id=user_id,
        text=output,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )
    
    await send_current_task(update, context)
    
    if candidate_id and plan.get('checklist'):
        schedule_onboarding_reminders(user_id, candidate_id, plan.get('checklist', []), datetime.now())


async def send_onboarding_plan_to_user(user_id: int, plan: Dict[str, Any], candidate_id: int = None):
    """Отправляет план онбординга пользователю по user_id (без update, для вызова из offer_flow)"""
    bot = Bot(token=settings.telegram_bot_token)
    
    class FakeContext:
        def __init__(self):
            self.user_data = {}
    
    fake_context = FakeContext()
    set_onboarding_session(fake_context, plan, 0, candidate_id)
    
    if candidate_id:
        HRAgentFacade.start_onboarding(candidate_id)
        HRAgentFacade.save_onboarding_progress(candidate_id, 0, [])
    
    output = (
        "📋 **Онбординг открыт**\n\n"
        f"Дата начала: {plan.get('start_date_readable', '—')}\n"
        f"Задач: {len(plan.get('checklist', []))}\n"
        f"Встреч: {len(plan.get('meetings', []))}\n\n"
        "Я буду вести вас по шагам. В меню ниже можно открыть текущую задачу, "
        "посмотреть все задачи, встречи, прогресс или попросить помощь."
    )
    
    await bot.send_message(
        chat_id=user_id,
        text=output,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )
    
    if not hasattr(send_onboarding_plan_to_user, 'user_sessions'):
        send_onboarding_plan_to_user.user_sessions = {}
    send_onboarding_plan_to_user.user_sessions[user_id] = {
        "plan": plan,
        "step": 0,
        "candidate_id": candidate_id,
        "completed_tasks": []
    }
    
    await send_current_task_to_user(user_id, plan, 0)
    
    if candidate_id and plan.get('checklist'):
        schedule_onboarding_reminders(user_id, candidate_id, plan.get('checklist', []), datetime.now())


async def send_current_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущую задачу пользователю (через update)"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    current_step = session.get("step", 0)
    checklist = plan.get("checklist", [])
    
    if current_step >= len(checklist):
        await send_onboarding_completed(update, context)
        return
    
    task = checklist[current_step]
    total = len(checklist)
    percent, progress_bar = get_progress_percent(context)
    
    message = (
        f"✅ **Текущая задача**\n\n"
        f"Шаг {current_step + 1} из {total}\n\n"
        f"**Что сделать:**\n{task.get('task')}\n\n"
        f"**Дедлайн:** {task.get('deadline_readable')}\n"
        f"**Прогресс:** {progress_bar} {percent}%\n\n"
        f"Когда закончите, нажмите **✅ Выполнить текущую** в меню."
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_current_task_to_user(user_id: int, plan: Dict[str, Any], current_step: int = 0):
    """Отправляет текущую задачу пользователю по user_id (без update)"""
    bot = Bot(token=settings.telegram_bot_token)
    
    checklist = plan.get("checklist", [])
    
    if current_step >= len(checklist):
        await send_onboarding_completed_to_user(user_id)
        return
    
    task = checklist[current_step]
    total = len(checklist)
    
    percent = int(current_step / total * 100) if total else 0
    filled = percent // 10
    progress_bar = "█" * filled + "░" * (10 - filled)
    
    message = (
        f"✅ **Текущая задача**\n\n"
        f"Шаг {current_step + 1} из {total}\n\n"
        f"**Что сделать:**\n{task.get('task')}\n\n"
        f"**Дедлайн:** {task.get('deadline_readable')}\n"
        f"**Прогресс:** {progress_bar} {percent}%\n\n"
        f"Когда закончите, нажмите **✅ Выполнить текущую** в меню."
    )
    
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_task_help(update: Update, context: ContextTypes.DEFAULT_TYPE, task_index: int):
    """Отправляет подробную помощь по задаче"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    checklist = plan.get("checklist", [])
    
    if task_index - 1 >= len(checklist):
        return
    
    task = checklist[task_index - 1]
    task_text = task.get('task', '')
    
    department_key = plan.get("department_key")
    help_data = get_task_help(task_text, department_key)
    
    message = (
        f"❓ **Как выполнить задачу:**\n\n"
        f"📌 **Задача:** {task_text}\n\n"
        f"🎯 **Смысл шага:** {help_data.get('task', 'Разобраться с задачей и довести её до результата.')}\n\n"
        f"📖 **Подробнее:** {help_data.get('details', '')}\n\n"
        f"📍 **Куда подойти:** {help_data.get('location', 'Уточните у HR или наставника')}\n"
        f"👤 **К кому обратиться:** {help_data.get('contact', 'Наставник или HR')}\n"
        f"☎️ **Телефон:** {help_data.get('phone', '+7 900 000-00-00')}\n\n"
        f"🧾 **Что подготовить:**\n" + "\n".join(help_data.get('prepare', ['• Блокнот или заметки', '• Паспорт, если задача связана с оформлением'])) + "\n\n"
        f"💡 **Советы:**\n" + "\n".join(help_data.get('tips', [])) + "\n\n"
        f"✅ **Готово, когда:** {help_data.get('done_when', 'вы поняли, что нужно сделать дальше, и согласовали результат с ответственным.')}\n\n"
        f"После выполнения нажмите **✅ Выполнить текущую**."
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_current_task_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет помощь именно по текущей задаче онбординга."""
    session = get_onboarding_session(context)
    if not session:
        return

    current_step = session.get("step", 0)
    await send_task_help(update, context, current_step + 1)


async def send_current_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущую встречу из плана"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    meetings = plan.get("meetings", [])
    current_idx = session.get("current_meeting", 0)
    
    if not meetings:
        await send_no_meetings_message(update)
        return
    
    if current_idx >= len(meetings):
        current_idx = len(meetings) - 1
    
    meeting = meetings[current_idx]
    
    message = (
        f"📅 **Встреча №{current_idx + 1} из {len(meetings)}**\n\n"
        f"📆 **Дата:** {meeting.get('date_readable')}\n"
        f"⏰ **Время:** {meeting.get('time')}\n"
        f"👤 **С кем:** {meeting.get('with')}\n"
        f"📌 **Тема:** {meeting.get('topic')}\n\n"
        f"💡 *Подготовьте вопросы заранее!*"
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет список всех задач с прогрессом"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    checklist = plan.get("checklist", [])
    current_step = session.get("step", 0)
    
    if not checklist:
        await send_no_tasks_message(update)
        return
    
    output = ["📋 **Все задачи онбординга**", ""]
    
    for i, task in enumerate(checklist, 1):
        if i - 1 < current_step:
            status = "✅"
        elif i - 1 == current_step:
            status = "▶️"
        else:
            status = "⬜"
        
        output.append(f"{status} **{i}. {task.get('task')}**")
        output.append(f"   📅 Дедлайн: {task.get('deadline_readable')}")
        output.append("")
    
    percent, progress_bar = get_progress_percent(context)
    output.append(f"📊 **Прогресс:** {progress_bar} {percent}%")
    output.append(f"✅ Выполнено: {current_step} из {len(checklist)}")
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text="\n".join(output),
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_all_meetings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет список всех встреч"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    meetings = plan.get("meetings", [])
    
    if not meetings:
        await send_no_meetings_message(update)
        return
    
    output = ["👥 **Все встречи онбординга**", ""]
    for i, meeting in enumerate(meetings, 1):
        output.append(f"**{i}. {meeting.get('date_readable')} {meeting.get('time')}**")
        output.append(f"   👤 {meeting.get('with')}")
        output.append(f"   📌 {meeting.get('topic')}")
        output.append("")
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text="\n".join(output),
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_progress_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет статус прогресса"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    checklist = plan.get("checklist", [])
    current_step = session.get("step", 0)
    total = len(checklist)
    percent, progress_bar = get_progress_percent(context)
    
    if percent == 0:
        pace = "🔴 Ещё не начали!"
    elif percent < 30:
        pace = "🟡 Хороший старт, продолжайте!"
    elif percent < 70:
        pace = "🟢 Отличный темп!"
    else:
        pace = "🏆 Почти закончили!"
    
    message = (
        f"📊 **Прогресс онбординга**\n\n"
        f"┌{'─' * 20}┐\n"
        f"│ {progress_bar} │\n"
        f"└{'─' * 20}┘\n\n"
        f"✅ **Выполнено:** {current_step} из {total} задач\n"
        f"📈 **Прогресс:** {percent}%\n"
        f"🎯 **Оценка:** {pace}\n\n"
    )
    
    if current_step < total:
        next_task = checklist[current_step].get('task')
        message += f"⏭️ **Следующая задача:** {next_task}"
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_quick_help(update: Update):
    """Отправляет справку по командам"""
    user_id = update.effective_user.id
    topics = ", ".join(topic.capitalize() for topic in get_quick_answers().keys())
    help_text = (
        "❓ **Помощь по онбордингу**\n\n"
        "В меню доступны основные разделы:\n"
        "• **✅ Текущая задача** — что нужно сделать сейчас\n"
        "• **✅ Выполнить текущую** — отметить задачу готовой\n"
        "• **❓ Помощь по задаче** — куда идти, кому звонить и что подготовить\n"
        "• **📋 Все задачи** — вся карта онбординга\n"
        "• **👥 Все встречи** — расписание встреч\n"
        "• **📊 Прогресс** — сколько уже выполнено\n\n"
        "Быстрые темы для новичка:\n"
        f"{topics}\n\n"
        "Если что-то непонятно, напишите вопрос одним сообщением. "
        "Например: **где парковка**, **когда обед**, **как получить ноутбук**."
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=help_text,
        parse_mode="Markdown",
        reply_markup=get_faq_topics_keyboard()
    )


async def send_faq_answer(update: Update, answer: str, topic: str = None):
    """Отправляет ответ из базы знаний новичка."""
    user_id = update.effective_user.id
    title = f"❓ **{topic.capitalize()}**\n\n" if topic else ""

    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=f"{title}{answer}",
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def edit_faq_answer(update: Update, answer: str, topic: str):
    """Показывает ответ из базы знаний в сообщении с inline-темами."""
    query = update.callback_query
    await query.edit_message_text(
        text=f"❓ **{topic.capitalize()}**\n\n{answer}",
        parse_mode="Markdown",
        reply_markup=get_faq_topics_keyboard()
    )


def get_faq_answer_for_text(text: str) -> Optional[tuple[str, str]]:
    """Ищет ответ FAQ по названию темы или ключевым словам."""
    text_lower = text.lower().strip()
    quick_answers = get_quick_answers()

    for topic, answer in quick_answers.items():
        if topic in text_lower and answer:
            return topic, answer

    answer = find_answer_by_keywords(text_lower)
    if answer:
        return "ответ на вопрос", answer

    return None


async def send_no_tasks_message(update: Update):
    """Отправляет сообщение, что задач нет"""
    user_id = update.effective_user.id
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text="📭 У вас нет активных задач.\n\nЕсли вы только начали, обратитесь к HR.",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_no_meetings_message(update: Update):
    """Отправляет сообщение, что встреч нет"""
    user_id = update.effective_user.id
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text="📭 У вас нет запланированных встреч.\n\nОбратитесь к HR для согласования.",
        reply_markup=get_onboarding_reply_keyboard()
    )


async def send_onboarding_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет поздравление с завершением онбординга (через update)"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    completed_count = len(session.get("completed_tasks", []))
    candidate_id = session.get("candidate_id")
    
    if candidate_id:
        HRAgentFacade.complete_onboarding(candidate_id)
        cancel_onboarding_reminders(user_id)
    
    message = (
        f"🎉 **ПОЗДРАВЛЯЮ! ОНБОРДИНГ ЗАВЕРШЁН!** 🎉\n\n"
        f"Вы успешно выполнили **{completed_count}** задач и готовы к полноценной работе!\n\n"
        f"🌟 **Что дальше?**\n"
        f"• Внедряйте полученные знания в работу\n"
        f"• Не стесняйтесь задавать вопросы коллегам\n"
        f"• Участвуйте в жизни команды\n\n"
        f"🚀 Добро пожаловать в команду! Желаю успехов!"
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown"
    )
    
    clear_onboarding_session(context)


async def send_onboarding_completed_to_user(user_id: int):
    """Отправляет поздравление с завершением онбординга по user_id (без update)"""
    bot = Bot(token=settings.telegram_bot_token)
    
    message = (
        f"🎉 **ПОЗДРАВЛЯЮ! ОНБОРДИНГ ЗАВЕРШЁН!** 🎉\n\n"
        f"Вы успешно выполнили все задачи и готовы к полноценной работе!\n\n"
        f"🌟 **Что дальше?**\n"
        f"• Внедряйте полученные знания в работу\n"
        f"• Не стесняйтесь задавать вопросы коллегам\n"
        f"• Участвуйте в жизни команды\n\n"
        f"🚀 Добро пожаловать в команду! Желаю успехов!"
    )
    
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown"
    )


async def mark_current_task_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмечает текущую задачу как выполненную"""
    user_id = update.effective_user.id
    session = get_onboarding_session(context)
    if not session:
        return
    
    plan = session.get("plan", {})
    current_step = session.get("step", 0)
    checklist = plan.get("checklist", [])
    
    if current_step >= len(checklist):
        await send_onboarding_completed(update, context)
        return
    
    task = checklist[current_step]
    
    mark_task_completed(context, current_step, task.get('task'))
    
    bot = Bot(token=settings.telegram_bot_token)
    next_step = current_step + 1
    total = len(checklist)
    percent = int(next_step / total * 100) if total else 100

    if next_step >= total:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "✅ **Задача выполнена**\n\n"
                f"{task.get('task')}\n\n"
                "Это была последняя задача онбординга."
            ),
            parse_mode="Markdown",
            reply_markup=get_onboarding_reply_keyboard()
        )
        await send_onboarding_completed(update, context)
        return
    
    await bot.send_message(
        chat_id=user_id,
        text=(
            "✅ **Задача выполнена**\n\n"
            f"{task.get('task')}\n\n"
            f"Прогресс: {next_step} из {total} задач ({percent}%).\n"
            "Следующий шаг доступен в меню: **✅ Текущая задача**."
        ),
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )


TASK_HELP_TEXT = {
    "default": {
        "task": "Понять, что ожидается по задаче, и выполнить её без лишней суеты.",
        "details": "Если формулировка задачи кажется общей, начните с короткого уточнения у наставника: какой результат нужен и где его показать.",
        "location": "3 этаж, кабинет 305, зона наставников",
        "contact": "Наставник адаптации: Анна Смирнова",
        "phone": "+7 900 101-10-01",
        "prepare": [
            "• Откройте текущий план онбординга",
            "• Выпишите 2-3 вопроса, если задача непонятна",
            "• Возьмите ноутбук или блокнот для заметок"
        ],
        "tips": [
            "• Не пытайтесь угадать ожидания, лучше уточнить сразу",
            "• После разговора коротко зафиксируйте договорённость",
            "• Если ответственный занят, напишите ему в корпоративный чат"
        ],
        "done_when": "вы понимаете следующий шаг и знаете, кому показать результат."
    },
    "доступ": {
        "task": "Получить рабочие доступы и проверить, что они действительно открываются.",
        "details": "Вам могут понадобиться корпоративная почта, VPN, 1С/CRM/ATS, трекер задач, файловое хранилище и внутренний портал. Не просто получите логины, а проверьте вход в каждую систему.",
        "location": "2 этаж, кабинет 205, IT-поддержка",
        "contact": "IT-специалист: Павел Орлов",
        "phone": "+7 900 202-20-02",
        "prepare": [
            "• Паспорт",
            "• Личный телефон для двухфакторной авторизации",
            "• Корпоративную почту, если её уже выдали"
        ],
        "tips": [
            "• Сразу проверьте VPN и почту",
            "• Не отправляйте пароли в мессенджерах",
            "• Если доступ не работает, попросите IT создать заявку и номер обращения"
        ],
        "done_when": "вы вошли во все нужные системы и знаете, куда писать при проблемах с доступом."
    },
    "документация": {
        "task": "Понять основные правила работы и найти документы, к которым нужно возвращаться.",
        "details": "Обычно важно посмотреть регламент рабочего времени, правила отпусков, инструкции по безопасности, должностную инструкцию и документы отдела.",
        "location": "3 этаж, кабинет 302, HR-отдел",
        "contact": "HR-специалист: Мария Кузнецова",
        "phone": "+7 900 303-30-03",
        "prepare": [
            "• Корпоративную почту",
            "• Доступ к внутреннему порталу",
            "• Список вопросов по правилам компании"
        ],
        "tips": [
            "• Начните с коротких регламентов, потом переходите к большим документам",
            "• Сохраните ссылки на важные документы",
            "• Отдельно уточните, какие правила критичны именно для вашей роли"
        ],
        "done_when": "вы нашли основные документы, сохранили ссылки и уточнили непонятные правила."
    },
    "команда": {
        "task": "Познакомиться с людьми, к которым вы будете чаще всего обращаться.",
        "details": "Важно понять не только имена коллег, но и зоны ответственности: кто помогает с задачами, кто согласует результат, кто отвечает за процессы.",
        "location": "4 этаж, переговорная 401 или рабочая зона отдела",
        "contact": "Руководитель команды: Ирина Волкова",
        "phone": "+7 900 404-40-04",
        "prepare": [
            "• Короткий рассказ о себе на 1 минуту",
            "• Вопросы о процессах команды",
            "• Блокнот для имён и зон ответственности"
        ],
        "tips": [
            "• Спросите, кто будет вашим основным наставником",
            "• Запишите, к кому идти по рабочим, техническим и организационным вопросам",
            "• Не стесняйтесь попросить добавить вас в рабочие чаты"
        ],
        "done_when": "вы знаете ключевых коллег, наставника и основные рабочие чаты."
    },
    "техника": {
        "task": "Получить и настроить рабочее оборудование.",
        "details": "Проверьте ноутбук, зарядку, монитор, мышь, клавиатуру, доступ к принтеру и базовые программы.",
        "location": "2 этаж, кабинет 205, IT-поддержка",
        "contact": "IT-специалист: Павел Орлов",
        "phone": "+7 900 202-20-02",
        "prepare": [
            "• Паспорт",
            "• Телефон для подтверждения учётной записи",
            "• Список программ, которые нужны для вашей должности"
        ],
        "tips": [
            "• Проверьте зарядку и подключение к Wi-Fi сразу на месте",
            "• Попросите показать, куда обращаться при поломке",
            "• Уточните правила установки сторонних программ"
        ],
        "done_when": "оборудование выдано, включается, подключено к сети и готово к работе."
    },
    "1с": {
        "task": "Получить доступ к 1С и понять свой участок работы.",
        "details": "Для бухгалтерии важно проверить права доступа, список организаций, участки учёта, ЭДО и папки с первичными документами.",
        "location": "3 этаж, кабинет 318, бухгалтерия",
        "contact": "Главный бухгалтер: Ольга Соколова",
        "phone": "+7 900 505-50-05",
        "prepare": [
            "• Корпоративную учётную запись",
            "• Паспорт для подтверждения личности",
            "• Список операций, которые нужно будет выполнять"
        ],
        "tips": [
            "• Сначала работайте только в тестовой базе, если она есть",
            "• Уточните, какие документы нельзя проводить без проверки",
            "• Запишите сроки ближайшей отчётности"
        ],
        "done_when": "вы вошли в 1С, видите нужные разделы и понимаете, какие операции можно выполнять самостоятельно."
    },
    "crm": {
        "task": "Разобраться с CRM и правилами ведения клиентов или кандидатов.",
        "details": "Проверьте доступ, карточки клиентов/кандидатов, стадии воронки, обязательные поля и правила комментариев.",
        "location": "4 этаж, кабинет 412, отдел продаж/HR",
        "contact": "Администратор CRM: Елена Фролова",
        "phone": "+7 900 606-60-06",
        "prepare": [
            "• Корпоративную почту",
            "• Пример карточки клиента или кандидата",
            "• Вопросы по стадиям процесса"
        ],
        "tips": [
            "• Не меняйте реальные карточки без согласования",
            "• Попросите показать хорошую заполненную карточку",
            "• Уточните, какие поля обязательны для отчётности"
        ],
        "done_when": "вы можете открыть CRM, найти нужную карточку и понимаете правила её заполнения."
    },
    "эдо": {
        "task": "Понять, как компания работает с электронными документами.",
        "details": "Нужно проверить доступ к ЭДО, правила подписания, маршруты согласования и ответственных за оригиналы.",
        "location": "3 этаж, кабинет 318, бухгалтерия",
        "contact": "Специалист по документообороту: Наталья Белова",
        "phone": "+7 900 707-70-07",
        "prepare": [
            "• Корпоративную почту",
            "• Доступ к ЭДО",
            "• Пример документа для проверки маршрута"
        ],
        "tips": [
            "• Уточните, какие документы подписывает только руководитель",
            "• Проверьте уведомления по новым документам",
            "• Запишите, где хранятся оригиналы"
        ],
        "done_when": "вы понимаете путь документа от получения до подписания или архива."
    }
}


DEPARTMENT_HELP_CONTEXT = {
    "development": {
        "name": "технического отдела",
        "location": "рабочая зона разработки / кабинет наставника",
        "contact": "технический наставник или руководитель команды",
        "phone": "+7 900 202-20-02",
        "systems": "Git, трекер задач, VPN, стенды, документация проекта и корпоративная почта",
        "focus": "разобраться в проекте, окружении, правилах задач и ревью",
        "safe_first_step": "запустите проект по README и покажите наставнику первый результат",
    },
    "finance": {
        "name": "бухгалтерии и финансов",
        "location": "бухгалтерия, кабинет 318",
        "contact": "главный бухгалтер или бухгалтер-наставник",
        "phone": "+7 900 505-50-05",
        "systems": "1С, ЭДО, банк-клиент, папки с первичкой и календарь отчётности",
        "focus": "понять свой участок учёта, документы, сроки и правила согласования",
        "safe_first_step": "сначала работайте с наставником и не проводите документы без проверки",
    },
    "hr": {
        "name": "HR-отдела",
        "location": "HR-зона / кабинет 302",
        "contact": "руководитель HR или рекрутер-наставник",
        "phone": "+7 900 303-30-03",
        "systems": "HRM/ATS, почта, календарь, шаблоны писем и кадровые папки",
        "focus": "понять этапы подбора, активные вакансии и правила коммуникации с кандидатами",
        "safe_first_step": "посмотрите несколько карточек кандидатов и согласуйте первый текст письма",
    },
    "sales": {
        "name": "отдела продаж",
        "location": "отдел продаж / зона наставника",
        "contact": "руководитель продаж или менеджер-наставник",
        "phone": "+7 900 606-60-06",
        "systems": "CRM, телефония, почта, база знаний, шаблоны КП и скрипты",
        "focus": "понять продукт, воронку, правила заполнения CRM и типовые возражения",
        "safe_first_step": "послушайте реальные звонки и заполните тестовую карточку клиента",
    },
    "marketing": {
        "name": "маркетинга",
        "location": "маркетинг / переговорная команды",
        "contact": "руководитель маркетинга или бренд-менеджер",
        "phone": "+7 900 707-70-07",
        "systems": "рекламные кабинеты, CRM, аналитика, соцсети и бренд-материалы",
        "focus": "понять ЦА, текущие кампании, бюджет, офферы и передачу лидов в продажи",
        "safe_first_step": "разберите одну активную кампанию и подготовьте короткие выводы",
    },
    "analytics": {
        "name": "аналитики",
        "location": "аналитический отдел / рабочая зона BI",
        "contact": "руководитель аналитики или аналитик-наставник",
        "phone": "+7 900 808-80-08",
        "systems": "BI, хранилище данных, отчёты, словарь метрик и документация источников",
        "focus": "понять метрики, источники данных и ограничения отчётов",
        "safe_first_step": "возьмите существующий дашборд и разберите, как считаются 2-3 показателя",
    },
    "legal": {
        "name": "юридического отдела",
        "location": "юридический отдел / архив договоров",
        "contact": "руководитель юротдела или юрист-наставник",
        "phone": "+7 900 909-90-09",
        "systems": "договорной архив, шаблоны, реестры, ЭДО и система согласования",
        "focus": "понять типовые договоры, маршруты согласования и рисковые условия",
        "safe_first_step": "проверьте один типовой договор по чек-листу вместе с наставником",
    },
    "design": {
        "name": "дизайна",
        "location": "дизайн-зона / Figma-файл команды",
        "contact": "руководитель дизайна или дизайнер-наставник",
        "phone": "+7 900 404-40-04",
        "systems": "Figma, дизайн-система, брендбук, таск-трекер и файловый архив",
        "focus": "понять стиль, компоненты, правила макетов и передачу в разработку",
        "safe_first_step": "откройте недавнюю задачу и повторите путь от брифа до финального макета",
    },
    "management": {
        "name": "управленческой роли",
        "location": "переговорная руководителя / рабочая зона команды",
        "contact": "непосредственный руководитель",
        "phone": "+7 900 101-10-01",
        "systems": "календарь, отчёты, задачи, документы, KPI и управленческие дашборды",
        "focus": "понять цели, людей, регулярные встречи, риски и текущие проекты",
        "safe_first_step": "проведите короткие 1:1 и соберите картину задач без резких изменений",
    },
}


def apply_department_context(help_data: Dict[str, Any], department_key: Optional[str]) -> Dict[str, Any]:
    """Делает универсальную подсказку конкретной для отдела."""
    context = DEPARTMENT_HELP_CONTEXT.get(department_key or "")
    if not context:
        return help_data

    result = help_data.copy()
    result["location"] = context["location"]
    result["contact"] = context["contact"]
    result["phone"] = context["phone"]
    result["details"] = (
        f"{help_data.get('details', '')}\n\n"
        f"Для {context['name']} особенно важно: {context['focus']}. "
        f"Основные системы: {context['systems']}."
    )
    result["prepare"] = [
        "• Корпоративную почту и доступ к рабочим системам",
        f"• Список вопросов по процессам {context['name']}",
        "• Блокнот или заметки для договорённостей",
    ]
    result["tips"] = [
        f"• Первый безопасный шаг: {context['safe_first_step']}",
        "• Уточните у ответственного, какой результат считается готовым",
        "• После выполнения коротко зафиксируйте итог в чате или задаче",
    ]
    result["done_when"] = (
        f"вы выполнили шаг с учётом процессов {context['name']} и понимаете, "
        "кому показать результат."
    )
    return result


def get_department_task_help(task_text: str, department_key: Optional[str]) -> Optional[Dict[str, Any]]:
    """Возвращает подсказку для профессиональных задач конкретного отдела."""
    context = DEPARTMENT_HELP_CONTEXT.get(department_key or "")
    if not context:
        return None

    task_lower = task_text.lower()
    professional_words = [
        "перв", "отчёт", "дашборд", "кампан", "звон", "клиент", "кандидат",
        "скрининг", "договор", "макет", "бренд", "метрик", "воронк", "kpi",
        "аудит", "план", "ревью", "бэклог", "проект", "задач", "процесс",
        "проводк", "платеж", "первичк", "контрагент",
    ]
    if not any(word in task_lower for word in professional_words):
        return None

    return {
        "task": f"Выполнить шаг не формально, а так, как принято в {context['name']}.",
        "details": (
            f"Эта задача относится к реальной работе {context['name']}. "
            f"Сначала разберитесь в контексте: {context['focus']}. "
            f"Затем сделайте небольшой безопасный результат и покажите ответственному."
        ),
        "location": context["location"],
        "contact": context["contact"],
        "phone": context["phone"],
        "prepare": [
            f"• Доступ к системам: {context['systems']}",
            "• Пример похожей выполненной задачи",
            "• 2-3 вопроса к наставнику по критериям готовности",
        ],
        "tips": [
            f"• {context['safe_first_step']}",
            "• Не меняйте реальные данные без согласования",
            "• Попросите показать хороший пример результата",
        ],
        "done_when": (
            "у вас есть понятный результат, он показан ответственному, "
            "и вы знаете следующий рабочий шаг."
        ),
    }


def get_task_help(task_text: str, department_key: Optional[str] = None) -> Dict[str, Any]:
    """Возвращает подробную помощь по задаче"""
    task_lower = task_text.lower()

    department_help = get_department_task_help(task_text, department_key)
    if department_help:
        return department_help
    
    if "1с" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["1с"], department_key)
    elif "эдо" in task_lower or "первич" in task_lower or "документооборот" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["эдо"], department_key)
    elif "crm" in task_lower or "клиент" in task_lower or "кандидат" in task_lower or "ats" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["crm"], department_key)
    elif "ноутбук" in task_lower or "оборудован" in task_lower or "техника" in task_lower or "рабочее место" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["техника"], department_key)
    elif "доступ" in task_lower or "получить" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["доступ"], department_key)
    elif "документ" in task_lower or "регламент" in task_lower or "изучить" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["документация"], department_key)
    elif "знаком" in task_lower or "команд" in task_lower:
        return apply_department_context(TASK_HELP_TEXT["команда"], department_key)
    else:
        return apply_department_context(TASK_HELP_TEXT["default"], department_key)


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки онбординга"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "onb_tasks":
        await send_all_tasks(update, context)
        
    elif data == "onb_meetings":
        await send_all_meetings(update, context)
        
    elif data == "onb_progress":
        await send_progress_status(update, context)
        
    elif data == "onb_help":
        await send_quick_help(update)

    elif data.startswith("onb_faq_"):
        topic_index = int(data.split("_")[2])
        quick_answers = list(get_quick_answers().items())
        if 0 <= topic_index < len(quick_answers):
            topic, answer = quick_answers[topic_index]
            await edit_faq_answer(update, answer, topic)
        else:
            await query.answer("Тема не найдена", show_alert=True)
        
    elif data == "onb_back_to_menu":
        await query.edit_message_text(
            text="📋 **Главное меню онбординга**\n\nВыберите действие:",
            reply_markup=get_onboarding_main_keyboard(),
            parse_mode="Markdown"
        )
        
    elif data == "onb_exit":
        await query.edit_message_text(
            text="👋 Онбординг сохранён. Вы можете вернуться в любой момент через кнопки меню.\n\nДо встречи!",
            reply_markup=None
        )
        
    elif data.startswith("onb_complete_"):
        task_num = int(data.split("_")[2])
        session = get_onboarding_session(context)
        if session and session.get("step", 0) + 1 == task_num:
            await mark_current_task_completed(update, context)
            await query.edit_message_reply_markup(reply_markup=None)
        else:
            await query.answer("❌ Эта задача уже выполнена или не текущая!", show_alert=True)
        
    elif data.startswith("onb_howto_"):
        task_num = int(data.split("_")[2])
        await send_task_help(update, context, task_num)
        
    elif data.startswith("onb_task_prev_"):
        current = int(data.split("_")[3])
        session = get_onboarding_session(context)
        if session:
            plan = session.get("plan", {})
            checklist = plan.get("checklist", [])
            new_idx = current - 2
            if new_idx >= 0:
                task = checklist[new_idx]
                message = (
                    f"📋 **Задача {current - 1} (для справки)**\n\n"
                    f"📌 {task.get('task')}\n"
                    f"📅 Дедлайн: {task.get('deadline_readable')}\n\n"
                    f"ℹ️ Это не текущая задача. Ваша текущая задача — #{session.get('step', 0) + 1}"
                )
                await query.edit_message_text(
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=get_task_navigation_keyboard(current - 1, len(checklist), task.get('task'))
                )
        
    elif data.startswith("onb_task_next_"):
        current = int(data.split("_")[3])
        session = get_onboarding_session(context)
        if session:
            plan = session.get("plan", {})
            checklist = plan.get("checklist", [])
            new_idx = current
            if new_idx < len(checklist):
                task = checklist[new_idx]
                message = (
                    f"📋 **Задача {current + 1} (для справки)**\n\n"
                    f"📌 {task.get('task')}\n"
                    f"📅 Дедлайн: {task.get('deadline_readable')}\n\n"
                    f"ℹ️ Это не текущая задача. Ваша текущая задача — #{session.get('step', 0) + 1}"
                )
                await query.edit_message_text(
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=get_task_navigation_keyboard(current + 1, len(checklist), task.get('task'))
                )
        
    elif data.startswith("onb_meeting_prev_"):
        current = int(data.split("_")[3])
        session = get_onboarding_session(context)
        if session:
            session["current_meeting"] = current - 1
            context.user_data["onboarding_session"] = session
            await send_current_meeting(update, context)
            
    elif data.startswith("onb_meeting_next_"):
        current = int(data.split("_")[3])
        session = get_onboarding_session(context)
        if session:
            session["current_meeting"] = current + 1
            context.user_data["onboarding_session"] = session
            await send_current_meeting(update, context)


async def process_onboarding_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает сообщения, связанные с онбордингом.
    Возвращает True, если сообщение было обработано как онбординг.
    """
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()
    
    session = get_onboarding_session(context)
    if not session:
        return False
    
    if text in [
        "готов", "готово", "done", "выполнил", "сделано", "выполнено", "+", "да", "ок",
        "✅ выполнить текущую", "✅ выполнить задачу", "✅ выполнено"
    ]:
        await mark_current_task_completed(update, context)
        return True
    
    elif text in ["задачи", "список", "tasks", "чеклист", "checklist", "все задачи", "мои задачи", "📋 все задачи", "📋 мои задачи"]:
        await send_all_tasks(update, context)
        return True
    
    elif text in ["встречи", "мои встречи", "meetings", "расписание", "календарь", "все встречи", "👥 все встречи", "📅 мои встречи"]:
        await send_all_meetings(update, context)
        return True
    
    elif text in ["помощь", "help", "?", "справка", "команды", "❓ помощь", "❓ задать вопрос"]:
        await send_quick_help(update)
        return True

    elif text in [
        "помощь по задаче", "как выполнить задачу", "как сделать задачу", "что подготовить",
        "куда подойти", "кому позвонить", "контакты по задаче", "❓ помощь по задаче"
    ]:
        await send_current_task_help(update, context)
        return True
    
    elif text in ["статус", "прогресс", "progress", "мой прогресс", "📊 прогресс", "📊 мой прогресс"]:
        await send_progress_status(update, context)
        return True
    
    elif text in ["текущая", "current", "что делать", "моя задача", "текущая задача", "✅ текущая задача"]:
        await send_current_task(update, context)
        return True

    faq_answer = get_faq_answer_for_text(text)
    if faq_answer:
        topic, answer = faq_answer
        await send_faq_answer(update, answer, topic)
        return True
    
    elif text.startswith("как") or text.startswith("что") or text.startswith("где") or text.startswith("когда") or text.startswith("почему"):
        await answer_question(update, text)
        return True
    
    if len(text) > 3 and text not in ["меню", "главное меню", "назад"]:
        await send_quick_help(update)
        return True
    
    return False


async def answer_question(update: Update, question: str):
    """Отвечает на вопрос кандидата (имитация помощи)"""
    user_id = update.effective_user.id
    question_lower = question.lower()
    
    if "куда" in question_lower or "кабинет" in question_lower or "офис" in question_lower:
        answer = "📍 **Где находится офис?**\n\nг. Челябинск, ул. Ленина, 5, офис 301.\n\n📍 **Мой кабинет/рабочее место?**\nУточните у администратора или HR при встрече."
    
    elif "когда" in question_lower or "во сколько" in question_lower:
        answer = "⏰ **Рабочий график:**\n• Начало работы: 09:00\n• Обед: 13:00-14:00\n• Окончание: 18:00\n\nПервую неделю рекомендуем приходить за 10-15 минут до начала."
    
    elif "кому" in question_lower or "наставник" in question_lower:
        answer = "👨‍🏫 **Ваш наставник:**\nОн будет помогать вам первую неделю. Уточните его имя у HR при встрече.\n\nНе стесняйтесь задавать ему вопросы!"
    
    elif "форма" in question_lower or "дресс-код" in question_lower:
        answer = "👔 **Дресс-код:**\nВ компании принят деловой стиль одежды.\n• Мужчины: рубашка/пиджак, брюки\n• Женщины: блузка/пиджак, юбка/брюки\n• Допускается smart casual по пятницам"
    
    elif "столовая" in question_lower or "поесть" in question_lower:
        answer = "🍽️ **Где пообедать?**\n• Столовая на 2-м этаже (с 12:00 до 15:00)\n• Кофе-поинт на каждом этаже\n• Рядом с офисом есть кафе: 'Вкусно и точка', 'Кофе Хаус'"
    
    elif "парковка" in question_lower:
        answer = "🚗 **Парковка:**\nДля сотрудников есть парковка за зданием. Вход с ул. Ленина. Необходимо получить пропуск в отделе безопасности."
    
    elif "техника" in question_lower or "ноутбук" in question_lower:
        answer = "💻 **Рабочая техника:**\nНоутбук и оборудование выдаются в IT-отделе (кабинет 205). Возьмите с собой паспорт."
    
    elif "привет" in question_lower or "здравствуй" in question_lower:
        answer = "👋 Привет! Я ваш помощник по онбордингу.\n\nЧем могу помочь? Могу:\n• Показать текущую задачу\n• Рассказать о встречах\n• Ответить на вопросы\n\nИспользуйте кнопки меню!"
    
    else:
        answer = "❓ **Я не совсем понял вопрос.**\n\nВот что я могу:\n• 📋 Показать задачи\n• 📅 Показать встречи\n• 📊 Показать прогресс\n• ❓ Ответить на частые вопросы\n\nВы можете уточнить свой вопрос или обратиться к HR."
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=user_id,
        text=answer,
        parse_mode="Markdown",
        reply_markup=get_onboarding_reply_keyboard()
    )
