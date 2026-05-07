"""app/bot/offer_flow.py
Оффер кандидату ("берем на работу...") и запуск онбординга
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.core.config import settings
from app.services.hr_facade import HRAgentFacade
from app.services.onboarding_generator import generate_onboarding_plan
from app.bot.onboarding_flow import send_onboarding_plan
from app.utils.email_sender import send_offer_email, send_offer_with_onboarding_link

logger = get_logger(__name__)


def parse_hire_message(text: str) -> Optional[Dict[str, Any]]:
    """
    Парсит сообщение HR вида:
    "взять 14 на разработчика Python с зп 150000"
    "взять Иванова Ивана на менеджера с зп 50000"
    """
    text_lower = text.lower()
    
    match = re.search(r'взять\s+(\d+)\s+на\s+(.+?)\s+с\s+зп\s*(\d+)', text_lower)
    if match:
        return {
            "candidate_id": int(match.group(1)),
            "position": match.group(2).strip().title(),
            "salary": int(match.group(3))
        }
    
    match = re.search(r'взять\s+([А-Яа-я\s]+?)\s+на\s+(.+?)\s+с\s+зп\s*(\d+)', text_lower)
    if match:
        name = match.group(1).strip().title()
        return {
            "candidate_name": name,
            "position": match.group(2).strip().title(),
            "salary": int(match.group(3))
        }
    
    match = re.search(r'нанять\s+кандидата\s+(\d+)\s+на\s+(.+?)\s+с\s+зп\s*(\d+)', text_lower)
    if match:
        return {
            "candidate_id": int(match.group(1)),
            "position": match.group(2).strip().title(),
            "salary": int(match.group(3))
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


def get_start_date_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с вариантами даты начала работы"""
    today = datetime.now().date()
    
    keyboard = []
    for i in range(1, 8):  # следующая неделя
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        keyboard.append([InlineKeyboardButton(f"📅 {date_str}", callback_data=f"start_date_{date.isoformat()}")])
    
    keyboard.append([InlineKeyboardButton("📅 Другая дата (введу вручную)", callback_data="start_date_manual")])
    
    return InlineKeyboardMarkup(keyboard)


async def send_offer_to_candidate(
    update: Update,
    candidate_id: int,
    candidate_name: str,
    position: str,
    salary: int
) -> bool:
    """
    Отправляет предложение работы кандидату с кнопками Согласен/Отказаться
    Отправляет ТОЛЬКО туда, откуда кандидат пришёл (Telegram ИЛИ email, НЕ оба сразу)
    Для email-кандидатов отправляет ссылку на бота для прохождения онбординга
    """
    candidate = HRAgentFacade.get_candidate(candidate_id)
    if not candidate:
        await update.message.reply_text(f"❌ Кандидат {candidate_name} не найден в базе")
        return False
    
    candidate_telegram_id = candidate.get('telegram_id')
    candidate_email = candidate.get('email')
    source = (candidate.get('source') or 'telegram').lower()  # откуда пришёл кандидат
    raw_data = candidate.get('raw_data')
    if source != 'email' and isinstance(raw_data, str) and '"source": "email"' in raw_data:
        source = 'email'
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Согласен", callback_data=f"offer_accept_{candidate_id}_{position}_{salary}"),
            InlineKeyboardButton("❌ Отказаться", callback_data=f"offer_decline_{candidate_id}")
        ]
    ])
    
    message = (
        f"🎉 **Предложение о работе!**\n\n"
        f"Здравствуйте, {candidate.get('name', candidate_name)}!\n\n"
        f"Мы рады предложить вам должность:\n\n"
        f"🎯 **Должность:** {position}\n"
        f"💰 **Заработная плата:** {salary:,} руб.\n\n"
        f"Вы согласны принять предложение?"
    )
    
    bot = Bot(token=settings.telegram_bot_token)
    
    sent = False
    send_method = None
    
    if source == 'email' and candidate_email:
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            
            email_sent = send_offer_with_onboarding_link(
                to_email=candidate_email,
                candidate_name=candidate.get('name', candidate_name),
                position=position,
                salary=salary,
                bot_username=bot_username,
                candidate_id=candidate_id
            )
            if email_sent:
                sent = True
                send_method = f"email ({candidate_email}) с ссылкой на бота"
                HRAgentFacade.update_candidate_status(
                    candidate_id,
                    "offered",
                    hired_position=position,
                    salary=salary
                )
                logger.info(f"✅ Оффер с ссылкой на онбординг отправлен на email {candidate_email}")
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
            send_method = "Telegram"
            logger.info(f"✅ Оффер отправлен в Telegram кандидату {candidate_name} (ID: {candidate_id})")
        except Exception as e:
            logger.error(f"Не удалось отправить оффер в Telegram: {e}")
    
    if not sent and candidate_email:
        try:
            bot_info = await bot.get_me()
            email_sent = send_offer_email(
                to_email=candidate_email,
                candidate_name=candidate.get('name', candidate_name),
                position=position,
                salary=salary,
                bot_username=bot_info.username,
                candidate_id=candidate_id
            )
            if email_sent:
                sent = True
                send_method = f"email ({candidate_email}) (fallback)"
                HRAgentFacade.update_candidate_status(
                    candidate_id,
                    "offered",
                    hired_position=position,
                    salary=salary
                )
                logger.info(f"✅ Оффер отправлен на email {candidate_email} (fallback)")
        except Exception as e:
            logger.error(f"Ошибка отправки email (fallback): {e}")
    
    if sent:
        if send_method == "Telegram":
            await update.message.reply_text(
                f"✅ Предложение отправлено кандидату **{candidate_name}** в Telegram\n\n"
                f"📌 Должность: {position}\n"
                f"💰 Зарплата: {salary:,} руб.\n\n"
                f"Ожидаем ответа..."
            )
        elif "email" in send_method:
            await update.message.reply_text(
                f"✅ Предложение отправлено кандидату **{candidate_name}** на {send_method}\n\n"
                f"📌 Должность: {position}\n"
                f"💰 Зарплата: {salary:,} руб.\n\n"
                f"📧 Кандидату отправлена ссылка на Telegram-бота для прохождения онбординга.\n"
                f"После перехода он сможет пошагово пройти адаптацию."
            )
        else:
            await update.message.reply_text(
                f"✅ Предложение отправлено кандидату **{candidate_name}**\n\n"
                f"📌 Должность: {position}\n"
                f"💰 Зарплата: {salary:,} руб.\n\n"
                f"Ожидаем ответа..."
            )
    else:
        await update.message.reply_text(
            f"❌ Не удалось отправить предложение кандидату {candidate_name}.\n\n"
            f"У кандидата нет Telegram ID и email, или произошла ошибка."
        )
        return False
    
    return True


async def handle_offer_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ кандидата на предложение работы (Согласен / Отказаться)"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    telegram_id = update.effective_user.id  # Telegram ID кандидата
    
    if data.startswith("offer_accept_"):
        parts = data.split("_")
        db_candidate_id = int(parts[2]) if len(parts) > 2 else None
        position = parts[3] if len(parts) > 3 else ""
        salary = int(parts[4]) if len(parts) > 4 else 0
        
        if not db_candidate_id:
            await query.edit_message_text("❌ Ошибка: не найден ID кандидата")
            return
        
        context.user_data["temp_data"] = context.user_data.get("temp_data", {})
        context.user_data["temp_data"]["pending_offer"] = {
            "db_candidate_id": db_candidate_id,
            "position": position,
            "salary": salary,
            "candidate_name": update.effective_user.first_name
        }
        
        await query.edit_message_text(
            "✅ **Отлично!**\n\n"
            "Пожалуйста, выберите дату, когда вы готовы выйти на работу:",
            reply_markup=get_start_date_keyboard(),
            parse_mode="Markdown"
        )
        
    elif data.startswith("offer_decline_"):
        parts = data.split("_")
        db_candidate_id = int(parts[2]) if len(parts) > 2 else None
        
        if db_candidate_id:
            HRAgentFacade.update_candidate_status(db_candidate_id, "rejected")
            HRAgentFacade.archive_candidate(db_candidate_id, "rejected")
        
        await query.edit_message_text(
            "❌ Вы отказались от предложения.\n\n"
            "Если передумаете — свяжитесь с HR."
        )
        
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.hr_telegram_id,
            text=f"❌ **Кандидат отказался от предложения!**\n\n👤 Telegram ID: {telegram_id}"
        )


async def handle_start_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор даты начала работы"""
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    data = query.data
    
    if data.startswith("start_date_"):
        date_str = data.replace("start_date_", "")
        
        if date_str == "manual":
            await query.edit_message_text(
                "📅 **Введите дату начала работы**\n\n"
                "Формат: ДД.ММ.ГГГГ\n"
                "Пример: 01.06.2025"
            )
            context.user_data["temp_data"] = context.user_data.get("temp_data", {})
            context.user_data["temp_data"]["awaiting_manual_date"] = True
            return
        
        start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        await finalize_offer(telegram_id, start_date, query, context)


async def finalize_offer(telegram_id: int, start_date, query, context):

    from app.services.candidate_service import get_candidate
    
    temp_data = context.user_data.get("temp_data", {})
    offer_data = temp_data.get("pending_offer", {})
    db_candidate_id = offer_data.get("db_candidate_id")
    position = offer_data.get("position")
    salary = offer_data.get("salary")
    
    if not db_candidate_id:
        await query.edit_message_text("❌ Ошибка: не найден ID кандидата в базе")
        return
    
    candidate = HRAgentFacade.get_candidate(db_candidate_id)
    if not candidate:
        await query.edit_message_text(f"❌ Кандидат с ID {db_candidate_id} не найден в базе данных")
        return
    
    if not candidate.get('telegram_id'):
        try:
            candidate['telegram_id'] = telegram_id
            HRAgentFacade.save_candidate(candidate, None)
            logger.info(f"✅ Telegram ID {telegram_id} привязан к кандидату {db_candidate_id}")
        except Exception as e:
            logger.error(f"Ошибка привязки Telegram ID: {e}")
    
    HRAgentFacade.update_candidate_status(
        db_candidate_id,
        "hired",
        hired_position=position,
        salary=salary,
        hired_at=start_date
    )
    
    HRAgentFacade.archive_candidate(db_candidate_id, "hired")
    logger.info(f"Кандидат {db_candidate_id} архивирован (причина: найм)")
    
    onboarding_plan = generate_onboarding_plan(
        candidate=candidate,
        department="development",
        level="middle",
        start_date=start_date.strftime("%Y-%m-%d")
    )
    
    date_display = start_date.strftime("%d.%m.%Y")
    
    await query.edit_message_text(
        f"🎉 **Поздравляем! Вы приняты на работу!**\n\n"
        f"🎯 Должность: {position}\n"
        f"💰 Зарплата: {salary:,} руб.\n"
        f"📅 Дата выхода: {date_display}\n\n"
        f"Теперь я открою для вас режим онбординга. "
        f"В основном меню появятся задачи, встречи, прогресс и помощь.",
        parse_mode="Markdown"
    )
    
    class FakeUpdate:
        def __init__(self, user_id):
            self.effective_user = type('obj', (object,), {'id': user_id})
            self.callback_query = None
            self.message = None
    
    fake_update = FakeUpdate(telegram_id)
    await send_onboarding_plan(fake_update, context, onboarding_plan, db_candidate_id)
    
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.hr_telegram_id,
        text=(
            f"✅ **Кандидат принял предложение!**\n\n"
            f"👤 {candidate.get('name')}\n"
            f"🆔 ID в БД: {db_candidate_id}\n"
            f"🎯 {position}\n"
            f"💰 {salary:,} руб.\n"
            f"📅 Дата выхода: {date_display}\n\n"
            f"📋 Онбординг запущен.\n"
            f"📦 Кандидат архивирован (причина: найм)\n"
            f"📱 Telegram ID привязан: {telegram_id}"
        ),
        parse_mode="Markdown"
    )
    if "temp_data" in context.user_data:
        temp = context.user_data["temp_data"]
        if "pending_offer" in temp:
            del temp["pending_offer"]
        if "awaiting_manual_date" in temp:
            del temp["awaiting_manual_date"]
