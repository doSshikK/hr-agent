"""
app/bot/schedule_manager.py
Управление расписанием собеседований (слоты) для HR
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.services.hr_facade import HRAgentFacade
from app.core.config import settings

logger = get_logger(__name__)


def parse_date(date_str: str) -> Optional[str]:
    """Парсит дату из формата DD.MM.YYYY или YYYY-MM-DD"""
    date_str = date_str.strip()
    
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    match = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return None


def format_slot_list(slots: List[Dict[str, Any]]) -> str:
    """Форматирует список слотов для вывода с именами кандидатов"""
    if not slots:
        return "📭 Нет добавленных слотов"
    
    output = ["📅 **Ваши слоты для собеседований:**", ""]
    
    slots_by_date = {}
    for slot in slots:
        date = slot.get('slot_date')
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)
    
    for date in sorted(slots_by_date.keys()):
        output.append(f"📆 **{date}:**")
        for slot in slots_by_date[date]:
            slot_time = slot.get('slot_time')
            is_booked = slot.get('is_booked', False)
            
            if is_booked:
                candidate_id = slot.get('candidate_id')
                candidate_name = "Неизвестно"
                if candidate_id:
                    candidate = HRAgentFacade.get_candidate(candidate_id)
                    if candidate:
                        candidate_name = candidate.get('name', 'Неизвестно')[:30]
                status = f"🔴 ЗАНЯТ ({candidate_name})"
            else:
                status = "🟢 СВОБОДЕН"
            
            output.append(f"   • {slot_time} — {status} (ID: {slot.get('id')})")
        output.append("")
    
    return "\n".join(output)


async def cmd_add_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление слота: /add_slot 2025-05-15 14:00"""
    user_id = update.effective_user.id
    
    if not settings.is_hr(user_id):
        await update.message.reply_text("❌ Только HR может управлять расписанием")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ **Использование:**\n"
            "`/add_slot 2025-05-15 14:00`\n"
            "`/add_slot 15.05.2025 14:00`\n\n"
            "📌 Формат даты: ГГГГ-ММ-ДД или ДД.ММ.ГГГГ\n"
            "📌 Формат времени: ЧЧ:ММ",
            parse_mode="Markdown"
        )
        return
    
    date_str = args[0]
    time_str = args[1]
    
    date = parse_date(date_str)
    if not date:
        await update.message.reply_text(f"❌ Неверный формат даты: {date_str}")
        return
    
    if not re.match(r'^\d{1,2}:\d{2}$', time_str):
        await update.message.reply_text(f"❌ Неверный формат времени: {time_str}\nИспользуйте ЧЧ:ММ")
        return
    
    time_str = time_str.zfill(5)  # 9:00 -> 09:00
    
    success, msg, slot_id = HRAgentFacade.add_interview_slot(user_id, date, time_str)
    
    if success:
        await update.message.reply_text(
            f"✅ **Слот добавлен!**\n\n"
            f"📅 Дата: {date}\n"
            f"⏰ Время: {time_str}\n"
            f"🆔 ID слота: {slot_id}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ {msg}")


async def cmd_my_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все слоты HR (и свободные, и занятые)"""
    user_id = update.effective_user.id
    
    if not settings.is_hr(user_id):
        await update.message.reply_text("❌ Только HR может просматривать расписание")
        return
    
    slots = HRAgentFacade.get_interview_slots_by_hr(user_id)
    
    if not slots:
        await update.message.reply_text(
            "📭 У вас нет добавленных слотов.\n\n"
            "Добавить слоты на день: нажмите '📅 Добавить день'"
        )
        return
    
    total = len(slots)
    free = sum(1 for s in slots if not s.get('is_booked'))
    booked = total - free
    
    message = format_slot_list(slots)  # уже показывает статус (🔴 ЗАНЯТ / 🟢 СВОБОДЕН)
    message += f"\n📊 **Статистика:**\n"
    message += f"   • Всего: {total}\n"
    message += f"   • Свободных: {free} 🟢\n"
    message += f"   • Занятых: {booked} 🔴\n\n"
    message += "🗑️ Удалить слот: `удалить слот 1` (где 1 — ID слота)"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_del_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление слота: /del_slot 1 (команда)"""
    user_id = update.effective_user.id
    
    if not settings.is_hr(user_id):
        await update.message.reply_text("❌ Только HR может управлять расписанием")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "❌ **Использование:** `/del_slot 1` (где 1 — ID слота)\n\n"
            "Узнать ID слотов: `/my_slots`",
            parse_mode="Markdown"
        )
        return
    
    try:
        slot_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID слота должен быть числом")
        return
    
    await cmd_del_slot_text(update, context, slot_id)


async def cmd_del_slot_text(update: Update, context: ContextTypes.DEFAULT_TYPE, slot_id: int):
    """Удаление слота по ID (вызывается из handlers.py или из команды)"""
    user_id = update.effective_user.id
    
    if not settings.is_hr(user_id):
        await update.message.reply_text("❌ Только HR может управлять расписанием")
        return
    
    from app.bot.interview_flow import send_slot_cancelled_notification
    
    slot = HRAgentFacade.get_interview_slot_by_id(slot_id)
    if not slot:
        await update.message.reply_text(f"❌ Слот с ID {slot_id} не найден")
        return
    
    if not slot.get('is_booked'):
        success, msg = HRAgentFacade.delete_interview_slot(slot_id, user_id)
        if success:
            await update.message.reply_text(f"✅ {msg}")
        else:
            await update.message.reply_text(f"❌ {msg}")
        return
    
    success, msg, candidate_id = HRAgentFacade.cancel_interview_booking(slot_id, user_id)
    
    if success:
        if candidate_id:
            HRAgentFacade.update_candidate_status(
                candidate_id,
                interview_stage=None,
                selected_slot_id=None
            )
            logger.info(f"✅ Статус кандидата {candidate_id} сброшен (interview_stage=None)")
        
        await update.message.reply_text(
            f"✅ {msg}\n\n"
            f"📧 Кандидату отправлено уведомление с предложением выбрать новую дату.\n"
            f"🔄 Статус кандидата сброшен, теперь его можно пригласить снова."
        )
        
        if candidate_id:
            await send_slot_cancelled_notification(update, candidate_id, slot)
    else:
        await update.message.reply_text(f"❌ {msg}")


async def cmd_clear_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка даты: удаляет ВСЕ свободные слоты на выбранную дату"""
    user_id = update.effective_user.id
    
    if not settings.is_hr(user_id):
        await update.message.reply_text("❌ Только HR может управлять расписанием")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "❌ **Использование:** `/clear_date 2025-05-15`\n"
            "`/clear_date 15.05.2025`\n\n"
            "Удаляет ВСЕ свободные слоты на указанную дату.\n"
            "Занятые слоты НЕ удаляются.",
            parse_mode="Markdown"
        )
        return
    
    date_str = args[0]
    date = parse_date(date_str)
    if not date:
        await update.message.reply_text(f"❌ Неверный формат даты: {date_str}")
        return
    
    slots = HRAgentFacade.get_interview_slots_by_date(date, user_id)
    if not slots:
        await update.message.reply_text(f"📭 На дату {date} нет слотов")
        return
    
    deleted, booked, errors = HRAgentFacade.delete_free_slots_by_date(date, user_id)
    
    if deleted > 0:
        message = f"✅ **Очистка даты {date}**\n\n"
        message += f"🗑️ Удалено свободных слотов: {deleted}\n"
        message += f"🔒 Оставлено занятых слотов: {booked}\n"
        if errors:
            message += f"⚠️ Ошибки: {', '.join(errors[:3])}\n"
        await update.message.reply_text(message, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ На дату {date} нет свободных слотов для удаления.\n\n"
            f"Все слоты либо заняты ({booked} шт.), либо их нет.",
            parse_mode="Markdown"
        )


def get_slots_calendar_keyboard(limit_days: int = 30) -> Optional[InlineKeyboardMarkup]:
    """
    Создаёт клавиатуру-календарь со свободными слотами для кандидатов
    """
    grouped_slots = HRAgentFacade.get_free_slots_grouped_by_date(limit_days)
    
    if not grouped_slots:
        return None
    
    keyboard = []
    for date, slots in grouped_slots.items():
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m.%Y")
        button_text = f"📅 {date_display} ({len(slots)} слотов)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"slots_date_{date}")])
    
    return InlineKeyboardMarkup(keyboard)


def get_slots_for_date_keyboard(date: str, slots: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с доступными слотами на конкретную дату"""
    keyboard = []
    row = []
    
    for i, slot in enumerate(slots):
        button_text = slot['slot_time']
        row.append(InlineKeyboardButton(button_text, callback_data=f"book_slot_{slot['id']}"))
        
        if (i + 1) % 4 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("◀️ Назад к датам", callback_data="slots_back_to_calendar")])
    
    return InlineKeyboardMarkup(keyboard)
