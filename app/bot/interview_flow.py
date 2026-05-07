"""
app/bot/interview_flow.py
Приглашение на собеседование, выбор слота, бронирование, отмена и изменение времени
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.core.config import settings
from app.services.hr_facade import HRAgentFacade
from app.bot.schedule_manager import get_slots_for_date_keyboard, get_slots_calendar_keyboard
from app.utils.email_sender import send_interview_invite_email

logger = get_logger(__name__)


def parse_invite_message(text: str) -> Optional[Dict[str, Any]]:
    """
    Парсит сообщение HR вида:
    "пригласить Иванова Ивана на собеседование"
    "пригласить кандидата 3 на собеседование"
    "пригласить Иванова на должность разработчика"
    """
    text_lower = text.lower()
    invite_word_pattern = r'(?:пригл[а-я]*|invite)'
    
    patterns = [
        rf'{invite_word_pattern}\s+кандидата\s+(\d+)\s+на\s+собеседование',
        rf'{invite_word_pattern}\s+кандидата\s+(\d+)\s+на\s+должность\s+(.+)',
        rf'{invite_word_pattern}\s+([А-Яа-я\s]+?)\s+на\s+собеседование\s+на\s+должность\s+(.+)',
        rf'{invite_word_pattern}\s+([А-Яа-я\s]+?)\s+на\s+собеседование',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            if len(groups) >= 1 and groups[0].isdigit():
                return {
                    "candidate_id": int(groups[0]),
                    "position": groups[1] if len(groups) > 1 else None
                }
            else:
                candidate_name = groups[0].strip()
                if candidate_name in {"его", "ее", "её", "их"}:
                    return None
                return {
                    "candidate_name": candidate_name.title(),
                    "position": groups[1] if len(groups) > 1 else None
                }
    
    return None


def find_candidate_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Находит кандидата по имени (частичное совпадение)"""
    candidates = HRAgentFacade.get_all_candidates(limit=1000)
    name_lower = name.lower()
    
    for cand in candidates:
        cand_name = cand.get('name', '').lower()
        if name_lower == cand_name or name_lower in cand_name or cand_name in name_lower:
            return cand
    
    return None


async def send_invite_to_candidate(
    update: Update,
    candidate_id: int,
    candidate_name: str,
    position: str = None
) -> bool:
    """
    Отправляет кандидату приглашение на собеседование с кнопками
    """
    candidate = HRAgentFacade.get_candidate(candidate_id)
    if not candidate:
        await update.message.reply_text(f"❌ Кандидат {candidate_name} не найден в базе")
        return False
    
    candidate_telegram_id = candidate.get('telegram_id')
    candidate_email = candidate.get('email')
    source = (candidate.get('source') or 'telegram').lower()
    raw_data = candidate.get('raw_data')
    if source != 'email' and isinstance(raw_data, str) and '"source": "email"' in raw_data:
        source = 'email'
    
    logger.info(f"📋 Данные кандидата: telegram_id={candidate_telegram_id}, email={candidate_email}, source={source}")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"invite_accept_{candidate_id}"),
            InlineKeyboardButton("❌ Отказаться", callback_data=f"invite_decline_{candidate_id}")
        ]
    ])
    
    position_text = f" на должность **{position}**" if position else ""
    
    message = (
        f"📅 **Приглашение на собеседование**{position_text}\n\n"
        f"Здравствуйте, {candidate.get('name', candidate_name)}!\n\n"
        f"Нам понравилось ваше резюме, и мы хотели бы пригласить вас на собеседование.\n\n"
        f"Пожалуйста, выберите действие:"
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    
    sent = False
    
    if source == 'email' and candidate_email:
        try:
            bot_info = await bot.get_me()
            email_sent = send_interview_invite_email(
                to_email=candidate_email,
                candidate_name=candidate.get('name', candidate_name),
                position=position,
                bot_username=bot_info.username,
                candidate_id=candidate_id
            )
            if email_sent:
                sent = True
                logger.info(f"✅ Приглашение отправлено на email {candidate_email}")
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")

    if not sent and source == 'telegram' and candidate_telegram_id:
        try:
            await bot.send_message(
                chat_id=candidate_telegram_id,
                text=message,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            sent = True
            logger.info(f"✅ Приглашение отправлено в Telegram кандидату {candidate_name} (ID: {candidate_id})")
        except Exception as e:
            logger.error(f"Не удалось отправить приглашение в Telegram: {e}")
    
    if not sent and candidate_email:
        try:
            bot_info = await bot.get_me()
            email_sent = send_interview_invite_email(
                to_email=candidate_email,
                candidate_name=candidate.get('name', candidate_name),
                position=position,
                bot_username=bot_info.username,
                candidate_id=candidate_id
            )
            if email_sent:
                sent = True
                logger.info(f"✅ Приглашение отправлено на email {candidate_email}")
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
    
    HRAgentFacade.update_candidate_status(candidate_id, status=None, interview_stage="invited")
    
    if sent:
        await update.message.reply_text(
            f"✅ Приглашение отправлено кандидату **{candidate_name}**!\n\n"
            f"Кандидат выберет удобное время."
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось отправить приглашение кандидату {candidate_name}.\n\n"
            f"У кандидата нет Telegram ID и email, или произошла ошибка."
        )
        return False
    
    return True


async def handle_invite_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ кандидата на приглашение (Принять / Отказаться)"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    telegram_id = update.effective_user.id
    
    if data.startswith("invite_accept_"):
        calendar_keyboard = get_slots_calendar_keyboard()
        
        if not calendar_keyboard:
            await query.edit_message_text(
                "❌ К сожалению, нет свободных слотов для собеседования.\n\n"
                "Пожалуйста, свяжитесь с HR для уточнения даты."
            )
            return
        
        await query.edit_message_text(
            "✅ **Отлично!**\n\n"
            "Пожалуйста, выберите удобную дату и время для собеседования:",
            reply_markup=calendar_keyboard,
            parse_mode="Markdown"
        )
        
        context.user_data["temp_data"] = context.user_data.get("temp_data", {})
        context.user_data["temp_data"]["invite_accepted"] = True
        
    elif data.startswith("invite_decline_"):
        await query.edit_message_text(
            "❌ Вы отказались от собеседования.\n\n"
            "Если передумаете — HR может отправить приглашение повторно."
        )
        
        candidate = HRAgentFacade.get_candidate_by_telegram_id(telegram_id)
        if candidate:
            HRAgentFacade.update_candidate_status(candidate['id'], status=None, interview_stage="declined")


async def handle_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор слота кандидатом из календаря"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    data = query.data
    
    if data.startswith("slots_date_"):
        date = data.replace("slots_date_", "")
        
        slots = HRAgentFacade.get_interview_slots_by_date(date)
        free_slots = [s for s in slots if not s.get('is_booked')]
        
        if not free_slots:
            calendar_keyboard = get_slots_calendar_keyboard()
            if calendar_keyboard:
                await query.edit_message_text(
                    f"❌ На {date} нет свободных слотов.\n\n"
                    f"Пожалуйста, выберите другую дату:",
                    reply_markup=calendar_keyboard,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ На {date} нет свободных слотов и других дат тоже нет.\n\n"
                    f"Пожалуйста, свяжитесь с HR."
                )
            return
        
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m.%Y")
        reply_markup = get_slots_for_date_keyboard(date, free_slots)
        
        await query.edit_message_text(
            f"📅 **Выберите время на {date_display}:**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    if data == "slots_back_to_calendar":
        calendar_keyboard = get_slots_calendar_keyboard()
        if calendar_keyboard:
            await query.edit_message_text(
                "📅 **Выберите удобную дату:**",
                reply_markup=calendar_keyboard,
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "❌ Нет свободных слотов для собеседования.\n\n"
                "Пожалуйста, свяжитесь с HR."
            )
        return
    
    if data.startswith("book_slot_"):
        slot_id = int(data.replace("book_slot_", ""))
        
        if settings.is_hr(telegram_id):
            await query.edit_message_text("❌ Вы не можете записаться на собеседование как HR")
            return
        
        candidate = HRAgentFacade.get_candidate_by_telegram_id(telegram_id)
        if not candidate:
            await query.edit_message_text("❌ Кандидат не найден в базе данных")
            return
        
        db_candidate_id = candidate['id']
        
        success, msg, slot_data = HRAgentFacade.book_interview_slot(slot_id, db_candidate_id)
        
        if not success:
            calendar_keyboard = get_slots_calendar_keyboard()
            if calendar_keyboard:
                await query.edit_message_text(
                    f"❌ {msg}\n\nПожалуйста, выберите другой слот:",
                    reply_markup=calendar_keyboard,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ {msg}\n\nНет других свободных слотов."
                )
            return
        
        HRAgentFacade.update_candidate_status(db_candidate_id, status=None, interview_stage="scheduled", selected_slot_id=slot_id)
        
        date = slot_data['date']
        time = slot_data['time']
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m.%Y")
        
        message = (
            f"✅ **Вы записаны на собеседование!**\n\n"
            f"📅 **Дата:** {date_display}\n"
            f"⏰ **Время:** {time}\n"
            f"📍 **Адрес:** г. Челябинск, ул. Ленина, 5, офис 301\n\n"
            f"📄 **При себе:**\n"
            f"   • Паспорт\n"
            f"   • Распечатанное резюме\n\n"
            f"❌ Если не сможете прийти, напишите 'отменить собеседование'\n"
            f"✏️ Чтобы изменить время, напишите 'изменить время'"
        )
        
        await query.edit_message_text(message, parse_mode="Markdown")
        
        if "temp_data" in context.user_data:
            temp = context.user_data["temp_data"]
            if "invite_accepted" in temp:
                del temp["invite_accepted"]
        
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.hr_telegram_id,
            text=(
                f"✅ **Кандидат записался на собеседование!**\n\n"
                f"👤 {candidate.get('name')}\n"
                f"📅 {date_display}\n"
                f"⏰ {time}"
            ),
            parse_mode="Markdown"
        )


async def cancel_candidate_interview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кандидат отменяет своё собеседование"""
    telegram_id = update.effective_user.id
    
    candidate = HRAgentFacade.get_candidate_by_telegram_id(telegram_id)
    if not candidate:
        await update.message.reply_text("❌ Вы не зарегистрированы как кандидат")
        return
    
    db_candidate_id = candidate['id']
    
    slot = HRAgentFacade.get_candidate_interview_slot(db_candidate_id)
    
    if not slot:
        await update.message.reply_text("❌ У вас нет запланированных собеседований")
        return
    
    success, msg = HRAgentFacade.cancel_interview_by_candidate(slot['id'], db_candidate_id)
    
    if success:
        await update.message.reply_text(
            "✅ Вы отменили собеседование.\n\n"
            "Если захотите записаться снова — напишите HR."
        )
        
        HRAgentFacade.update_candidate_status(db_candidate_id, status=None, interview_stage="cancelled", selected_slot_id=None)
        
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.hr_telegram_id,
            text=(
                f"❌ **Кандидат отменил собеседование!**\n\n"
                f"👤 {candidate.get('name')}\n"
                f"📅 {slot.get('slot_date')} в {slot.get('slot_time')}"
            ),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ {msg}")


async def change_interview_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кандидат хочет изменить время собеседования"""
    telegram_id = update.effective_user.id
    
    candidate = HRAgentFacade.get_candidate_by_telegram_id(telegram_id)
    if not candidate:
        await update.message.reply_text("❌ Вы не зарегистрированы как кандидат")
        return
    
    db_candidate_id = candidate['id']
    
    slot = HRAgentFacade.get_candidate_interview_slot(db_candidate_id)
    
    if not slot:
        await update.message.reply_text("❌ У вас нет запланированных собеседований")
        return
    
    success, msg = HRAgentFacade.cancel_interview_by_candidate(slot['id'], db_candidate_id)
    
    if not success:
        await update.message.reply_text(f"❌ {msg}")
        return
    
    calendar_keyboard = get_slots_calendar_keyboard()
    
    if not calendar_keyboard:
        await update.message.reply_text(
            "❌ Нет свободных слотов для переноса.\n"
            "Пожалуйста, свяжитесь с HR."
        )
        return
    
    await update.message.reply_text(
        "✅ Старое время отменено.\n\n"
        "📅 **Пожалуйста, выберите новую удобную дату и время:**",
        reply_markup=calendar_keyboard
    )
    
    context.user_data["temp_data"] = context.user_data.get("temp_data", {})
    context.user_data["temp_data"]["changing_time"] = True
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.hr_telegram_id,
        text=(
            f"🔄 **Кандидат изменяет время собеседования!**\n\n"
            f"👤 {candidate.get('name')}\n"
            f"Старый слот: {slot.get('slot_date')} в {slot.get('slot_time')}\n"
            f"Ожидает выбора нового времени."
        ),
        parse_mode="Markdown"
    )


async def send_slot_cancelled_notification(
    update: Update,
    candidate_id: int,
    cancelled_slot: Dict[str, Any]
):
    """Отправляет кандидату уведомление об отмене слота и предлагает выбрать новый"""
    from telegram import Bot
    
    candidate = HRAgentFacade.get_candidate(candidate_id)
    if not candidate:
        logger.error(f"Кандидат {candidate_id} не найден")
        return
    
    candidate_telegram_id = candidate.get('telegram_id')
    if not candidate_telegram_id:
        logger.warning(f"У кандидата {candidate_id} нет Telegram ID")
        return
    
    bot = Bot(token=settings.telegram_bot_token)
    
    date = cancelled_slot.get('slot_date')
    time = cancelled_slot.get('slot_time')
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    date_display = date_obj.strftime("%d.%m.%Y")
    
    calendar_keyboard = get_slots_calendar_keyboard()
    
    if not calendar_keyboard:
        await bot.send_message(
            chat_id=candidate_telegram_id,
            text=(
                f"😔 **Извините, собеседование отменено!**\n\n"
                f"К сожалению, слот на {date_display} в {time} был отменён HR.\n\n"
                f"❌ Нет свободных слотов для перезаписи.\n"
                f"Пожалуйста, свяжитесь с HR."
            ),
            parse_mode="Markdown"
        )
        return
    
    await bot.send_message(
        chat_id=candidate_telegram_id,
        text=(
            f"😔 **Извините, собеседование отменено!**\n\n"
            f"К сожалению, слот на {date_display} в {time} был отменён HR.\n\n"
            f"📅 **Пожалуйста, выберите новую удобную дату и время:**"
        ),
        reply_markup=calendar_keyboard,
        parse_mode="Markdown"
    )
