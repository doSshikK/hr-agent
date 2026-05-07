"""Telegram бот для HR Agent - точка входа"""

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.request import HTTPXRequest

from app.core.config import settings
from app.agent.hr_agent import HRAgent
from app.core.logger import get_logger
from app.services.hr_facade import HRAgentFacade

from .commands import start
from .handlers import handle_message, handle_document
from .pagination import handle_pagination_callback
from .onboarding_flow import handle_onboarding_callback
from .middlewares import RoleMiddleware, LoggingMiddleware, ErrorHandlingMiddleware

logger = get_logger(__name__)

HR_CHAT_ID = None


async def send_notification_to_hr(message: str):
    """Отправляет уведомление HR в Telegram (администратору бота)"""
    global HR_CHAT_ID
    
    if HR_CHAT_ID is None:
        HR_CHAT_ID = settings.hr_telegram_id
    
    if HR_CHAT_ID and HR_CHAT_ID != 0:
        try:
            from telegram import Bot
            bot = Bot(token=settings.telegram_bot_token)
            await bot.send_message(chat_id=HR_CHAT_ID, text=message, parse_mode="Markdown")
            logger.info(f"✅ Уведомление отправлено HR (chat_id: {HR_CHAT_ID})")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление HR: {e}")
    else:
        logger.warning("⚠️ HR_TELEGRAM_ID не задан в настройках, уведомления не отправляются")


async def handle_callback(update: Update, context):
    """Единый обработчик всех callback'ов"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("onb_"):
        from app.bot.onboarding_flow import handle_onboarding_callback
        await handle_onboarding_callback(update, context)
        return
    
    if data.startswith("page_"):
        await handle_pagination_callback(update, context)
        return
    
    if data.startswith("offer_accept_") or data.startswith("offer_decline_"):
        from app.bot.offer_flow import handle_offer_response
        await handle_offer_response(update, context)
        return
    
    if data.startswith("start_date_"):
        from app.bot.offer_flow import handle_start_date_selection
        await handle_start_date_selection(update, context)
        return
    
    
    if data.startswith("invite_accept_") or data.startswith("invite_decline_"):
        from app.bot.interview_flow import handle_invite_response
        await handle_invite_response(update, context)
        return
    
    if data.startswith("slots_date_") or data.startswith("book_slot_") or data == "slots_back_to_calendar":
        from app.bot.interview_flow import handle_slot_selection
        await handle_slot_selection(update, context)
        return
    
    
    if data.startswith("slots_cal_prev_"):
        from app.bot.keyboards import get_slots_calendar_inline_keyboard
        parts = data.split("_")
        year = int(parts[3])
        month = int(parts[4])
        await query.message.reply_text(
            "📅 **Выберите дату:**",
            reply_markup=get_slots_calendar_inline_keyboard(year, month, hr_id=user_id)
        )
        await query.answer()
        try:
            await query.delete_message()
        except:
            pass
        return
    
    if data.startswith("slots_cal_next_"):
        from app.bot.keyboards import get_slots_calendar_inline_keyboard
        parts = data.split("_")
        year = int(parts[3])
        month = int(parts[4])
        await query.message.reply_text(
            "📅 **Выберите дату:**",
            reply_markup=get_slots_calendar_inline_keyboard(year, month, hr_id=user_id)
        )
        await query.answer()
        try:
            await query.delete_message()
        except:
            pass
        return
    
    if data.startswith("slots_add_date_"):
        date = data.replace("slots_add_date_", "")
        
        temp_data_local = context.user_data.get("temp_data", {})
        mode = temp_data_local.get("mode", "add")
        
        if mode == "clear_date":
            from app.bot.keyboards import get_slots_management_keyboard
            
            slots = HRAgentFacade.get_interview_slots_by_date(date, user_id)
            if not slots:
                await query.message.reply_text(
                    f"📭 На дату {date} нет слотов для удаления",
                    reply_markup=get_slots_management_keyboard()
                )
            else:
                deleted, booked, errors = HRAgentFacade.delete_free_slots_by_date(date, user_id)
                
                if deleted > 0:
                    await query.message.reply_text(
                        f"✅ **Очистка даты {date}**\n\n"
                        f"🗑️ Удалено свободных слотов: {deleted}\n"
                        f"🔒 Оставлено занятых слотов: {booked}",
                        reply_markup=get_slots_management_keyboard(),
                        parse_mode="Markdown"
                    )
                else:
                    await query.message.reply_text(
                        f"❌ На дату {date} нет свободных слотов для удаления.\n\n"
                        f"Все слоты либо заняты ({booked} шт.), либо их нет.",
                        reply_markup=get_slots_management_keyboard(),
                        parse_mode="Markdown"
                    )
            
            if "temp_data" in context.user_data:
                context.user_data["temp_data"].pop("mode", None)
            
            try:
                await query.delete_message()
            except:
                pass
            
            await query.answer()
            return
        
        from app.bot.keyboards import get_slots_time_keyboard
        await query.edit_message_text(
            f"📅 **Выберите время для {date}:**",
            reply_markup=get_slots_time_keyboard(date)
        )
        await query.answer()
        return
    
    if data.startswith("slots_add_time_"):
        from app.bot.keyboards import get_slots_time_keyboard
        
        parts = data.replace("slots_add_time_", "").split("_")
        date = parts[0]
        time = parts[1]
        
        if not settings.is_hr(user_id):
            await query.answer("❌ Только HR может добавлять слоты", show_alert=True)
            return
        
        success, msg, slot_id = HRAgentFacade.add_interview_slot(user_id, date, time)
        
        if success:
            await query.edit_message_text(
                f"✅ **Слот добавлен!**\n\n"
                f"📅 Дата: {date}\n"
                f"⏰ Время: {time}\n\n"
                f"➕ Добавить ещё? Используйте кнопки ниже.",
                reply_markup=get_slots_time_keyboard(date)
            )
        else:
            await query.edit_message_text(
                f"❌ {msg}\n\n"
                f"Попробуйте другое время.",
                reply_markup=get_slots_time_keyboard(date)
            )
        await query.answer()
        return
    
    if data.startswith("slots_add_full_day_"):
        from app.bot.keyboards import get_slots_calendar_inline_keyboard
        
        date = data.replace("slots_add_full_day_", "")
        
        if not settings.is_hr(user_id):
            await query.answer("❌ Только HR может добавлять слоты", show_alert=True)
            return
        
        added, errors = HRAgentFacade.generate_interview_slots_for_date(user_id, date, "09:00", "18:00", 60)
        
        if added > 0:
            await query.edit_message_text(
                f"✅ **Добавлено {added} слотов на {date}**\n\n"
                f"⏰ Время: с 09:00 до 18:00\n"
                f"📏 Шаг: 60 минут\n\n"
                f"📅 Чтобы добавить ещё, выберите дату:",
                reply_markup=get_slots_calendar_inline_keyboard(hr_id=user_id)
            )
        else:
            await query.edit_message_text(
                f"❌ Не удалось добавить слоты на {date}\n\n"
                f"Возможно, они уже существуют.\n\n"
                f"📅 Попробуйте другую дату:",
                reply_markup=get_slots_calendar_inline_keyboard(hr_id=user_id)
            )
        await query.answer()
        return
    
    if data == "slots_back_to_menu":
        from app.bot.keyboards import get_slots_management_keyboard
        await query.edit_message_text(
            "📅 **Управление слотами для собеседований**\n\n"
            "Выберите действие:",
            reply_markup=get_slots_management_keyboard()
        )
        await query.answer()
        return
    
    if data == "slots_back_to_calendar_hr":
        from app.bot.keyboards import get_slots_calendar_inline_keyboard
        await query.edit_message_text(
            "📅 **Выберите дату:**",
            reply_markup=get_slots_calendar_inline_keyboard(hr_id=user_id)
        )
        await query.answer()
        return
    
    if data == "ignore":
        await query.answer()
        return
    
    await query.answer()
    logger.warning(f"Неизвестный callback: {data}")


def main():
    """Запуск Telegram бота"""
    token = settings.telegram_bot_token
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в настройках")
        return
    
    hr_agent = HRAgent()
    
    request = HTTPXRequest(
        connect_timeout=settings.telegram_request_timeout,
        read_timeout=settings.telegram_request_timeout,
        write_timeout=settings.telegram_request_timeout,
        pool_timeout=settings.telegram_request_timeout
    )
    
    app = Application.builder().token(token).request(request).build()
    
    app.bot_data["hr_agent"] = hr_agent
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("=" * 60)
    print("🤖 HR Agent Бот запущен!")
    print("=" * 60)
    print("\n📋 Доступные команды:")
    print("")
    print("👥 **Кандидаты:**")
    print("   • добавить нового кандидата — пошаговое добавление")
    print("   • покажи кандидатов — список всех")
    print("   • инфо кандидат 1 — полная информация")
    print("   • редактировать кандидата 1 — редактирование")
    print("   • удалить кандидата 1 — удалить")
    print("   • удалить всех кандидатов — удалить всех")
    print("   • экспорт кандидата в pdf 1 — сохранить в PDF")
    print("   • архивировать кандидата 1 — отправить в архив")
    print("   • показать архив — посмотреть архив")
    print("   • восстановить из архива 1 — вернуть из архива")
    print("")
    print("💼 **Вакансии:**")
    print("   • добавить вакансию — пошаговое добавление")
    print("   • покажи вакансии — список всех")
    print("   • инфо вакансия 1 — полная информация")
    print("   • редактировать вакансию 1 — редактирование")
    print("   • удалить вакансию 1 — удалить")
    print("   • удалить все вакансии — удалить все")
    print("   • экспорт вакансии в pdf 1 — сохранить в PDF")
    print("")
    print("📝 **Тесты и онбординг:**")
    print("   • создай тест для frontend middle — генерация теста")
    print("   • экспорт теста в pdf — сохранить тест")
    print("   • сохранить тест в pdf имя.pdf — сохранить с именем")
    print("   • редактировать тест — изменить последний тест")
    print("   • сделай онбординг для Ивана — план адаптации")
    print("   • экспорт онбординга в pdf — сохранить план")
    print("   • редактировать онбординг — изменить план")
    print("")
    print("📅 **Управление собеседованиями (для HR):**")
    print("   • 📅 Управление собеседованиями — кнопка в главном меню")
    print("   • 📅 Добавить день — добавить слоты на выбранную дату")
    print("   • 📋 Мои слоты — показать все слоты")
    print("   • 🗑️ Удалить слот — удалить по ID")
    print("   • 🗑️ Очистить дату — удалить все свободные слоты на дату")
    print("   • пригласить ФИО на собеседование — пригласить кандидата")
    print("   • взять ФИО на должность с зп XXX — предложить работу")
    print("")
    print("📊 **Опросы:**")
    print("   • создай nps опрос — создание опроса")
    print("   • проанализируй опрос 1 — анализ результатов")
    print("   • покажи опросы — список опросов")
    print("   • удалить опрос 1 — удалить опрос")
    print("   • удалить все опросы — удалить все")
    print("")
    print("❌ **Отмена:**")
    print("   • отмена — прервать текущее действие")
    print("")
    print("=" * 60)
    
    async def post_init(application) -> None:
        try:
            from app.utils.reminder import start_reminder_service
            await start_reminder_service()
            logger.info("📅 Сервис напоминаний запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска сервиса напоминаний: {e}")

    app.post_init = post_init

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
