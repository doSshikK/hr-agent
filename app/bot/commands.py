"""Команды бота (/start, /cancel)"""

import json
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.services.hr_facade import HRAgentFacade
from app.core.config import settings
from .keyboards import get_main_keyboard, get_cancel_keyboard, get_candidate_keyboard
from app.services.onboarding_generator import generate_onboarding_plan
from app.bot.onboarding_flow import get_onboarding_reply_keyboard, send_onboarding_plan

logger = get_logger(__name__)


async def handle_candidate_portal_link(update: Update, context: ContextTypes.DEFAULT_TYPE, candidate_id: int):
    """Открывает нужный сценарий для email-кандидата по универсальной ссылке."""
    user_id = update.effective_user.id
    candidate = HRAgentFacade.get_candidate(candidate_id)

    if not candidate:
        await update.message.reply_text(
            "❌ Кандидат не найден. Пожалуйста, свяжитесь с HR."
        )
        return

    if not candidate.get("telegram_id") or candidate.get("telegram_id") != user_id:
        candidate["telegram_id"] = user_id
        HRAgentFacade.save_candidate(candidate, None)
        logger.info(f"✅ Telegram ID {user_id} привязан к кандидату {candidate_id}")

    status = candidate.get("status")
    interview_stage = candidate.get("interview_stage")
    name = candidate.get("name") or update.effective_user.first_name

    if interview_stage == "invited":
        from app.bot.schedule_manager import get_slots_calendar_keyboard

        calendar_keyboard = get_slots_calendar_keyboard()
        if not calendar_keyboard:
            await update.message.reply_text(
                f"Здравствуйте, {name}!\n\n"
                "Сейчас нет свободных слотов для собеседования. "
                "Пожалуйста, ответьте на письмо HR или позвоните по телефону +7 950 722-25-70."
            )
            return

        context.user_data["temp_data"] = context.user_data.get("temp_data", {})
        context.user_data["temp_data"]["invite_accepted"] = True

        await update.message.reply_text(
            f"Здравствуйте, {name}!\n\n"
            "Я нашёл ваше приглашение на собеседование. "
            "Выберите удобную дату и время:",
            reply_markup=calendar_keyboard,
            parse_mode="Markdown"
        )
        return

    if status == "offered":
        position = candidate.get("hired_position") or "сотрудник"
        salary = int(candidate.get("salary") or 0)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Принимаю", callback_data=f"offer_accept_{candidate_id}_{position}_{salary}"),
                InlineKeyboardButton("❌ Отказаться", callback_data=f"offer_decline_{candidate_id}"),
            ]
        ])

        await update.message.reply_text(
            f"🎉 **Предложение о работе**\n\n"
            f"Здравствуйте, {name}!\n\n"
            f"🎯 Должность: {position}\n"
            f"💰 Зарплата: {salary:,} руб.\n\n"
            "Если предложение вам подходит, нажмите **Принимаю**. "
            "После этого я помогу выбрать дату выхода.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    if status == "hired":
        onboarding_plan = generate_onboarding_plan(
            candidate=candidate,
            department="development",
            level="middle",
            start_date=datetime.now().strftime("%Y-%m-%d")
        )
        await send_onboarding_plan(update, context, onboarding_plan, candidate_id=candidate_id)
        return

    if interview_stage == "scheduled":
        await update.message.reply_text(
            f"Здравствуйте, {name}!\n\n"
            "Вы уже записаны на собеседование. Если нужно изменить время, напишите: изменить время."
        )
        return

    await update.message.reply_text(
        f"Здравствуйте, {name}!\n\n"
        "Я нашёл вашу заявку. Сейчас она находится на рассмотрении у HR. "
        "Если хотите уточнить статус, ответьте на письмо или позвоните HR: +7 950 722-25-70."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает /cancel и возвращает пользователя в подходящее меню."""
    context.user_data["user_state"] = {}
    context.user_data["temp_data"] = {}

    user_id = update.effective_user.id
    candidate = HRAgentFacade.get_candidate_by_telegram_id(user_id)
    if candidate and candidate.get("status") == "hired":
        await update.message.reply_text(
            "✅ Действие отменено. Вы остались в режиме онбординга.",
            reply_markup=get_onboarding_reply_keyboard()
        )
        return

    await update.message.reply_text("✅ Действие отменено.", reply_markup=get_candidate_keyboard())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user
        
        if settings.is_hr(user_id):
            context.user_data["role"] = "hr"
            context.user_data["is_hr"] = True
            logger.info(f"🔥 [START] Принудительно установлена роль HR для {user_id}")
        else:
            context.user_data["role"] = "candidate"
            context.user_data["is_hr"] = False
        
        is_hr_user = context.user_data.get("is_hr", False)
        if not is_hr_user:
            is_hr_user = settings.is_hr(user_id)
            if is_hr_user:
                context.user_data["role"] = "hr"
                context.user_data["is_hr"] = True
        
        logger.info(f"👤 [START] Пользователь {user_id}, is_hr={is_hr_user}")
        start_payload = context.args[0] if context.args else ""
        is_portal_link = (
            start_payload.startswith("candidate_")
            or start_payload.startswith("offer_")
            or start_payload.startswith("onboarding_")
        )
        
        if not is_hr_user and not is_portal_link:
            existing = HRAgentFacade.get_candidate_by_telegram_id(user_id)
            if not existing:
                HRAgentFacade.save_candidate({
                    "telegram_id": user_id,
                    "name": user.first_name,
                    "source": "telegram"
                }, None)
                logger.info(f"✅ Зарегистрирован новый кандидат: {user_id} ({user.first_name})")
            else:
                logger.info(f"✅ Кандидат {user_id} уже зарегистрирован")
        
        if start_payload.startswith(("candidate_", "offer_", "onboarding_")):
            try:
                candidate_id = int(start_payload.split("_", 1)[1])
                logger.info(f"🔗 Пользователь {user_id} перешёл по ссылке кандидата {candidate_id}")
                await handle_candidate_portal_link(update, context, candidate_id)
                return
                
            except ValueError as e:
                logger.error(f"Ошибка парсинга ID кандидата из ссылки: {e}")
                await update.message.reply_text(
                    "❌ Некорректная ссылка.\n\n"
                    "Пожалуйста, обратитесь в HR."
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при обработке ссылки онбординга: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка при открытии сценария.\n\n"
                    "Пожалуйста, попробуйте позже или свяжитесь с HR."
                )
                return
        
        if context.args and context.args[0].startswith("candidate"):
            context.user_data["user_state"] = {"state": "candidate_waiting_for_resume"}
            await update.message.reply_text(
                "📄 **Отправка резюме**\n\n"
                "Пожалуйста, отправьте файл с вашим резюме (PDF или DOCX).\n"
                "Мы добавим вас в базу кандидатов.\n\n"
                "❌ *Отмена* — чтобы прервать",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if context.args and context.args[0].startswith("survey_"):
            survey_id = int(context.args[0].split("_")[1])
            
            survey = HRAgentFacade.get_survey(survey_id)
            
            if not survey:
                await update.message.reply_text("❌ Опрос не найден")
                return
            
            survey_type = survey.get("type", "nps")
            
            context.user_data["user_state"] = {
                "state": "survey_waiting_for_score",
                "survey_id": survey_id,
                "survey_type": survey_type
            }
            
            if survey_type == "nps":
                await update.message.reply_text(
                    f"📊 **Опрос #{survey_id} (NPS)**\n\n"
                    f"Вопрос 1: Насколько вероятно, что вы порекомендуете компанию?\n"
                    f"Оцените от 0 до 10:"
                )
            else:  # pulse
                await update.message.reply_text(
                    f"📊 **Опрос #{survey_id} (Pulse)**\n\n"
                    f"Вопрос 1: Насколько вы удовлетворены своей работой?\n"
                    f"Оцените от 1 до 5:"
                )
            return
        
        
        if is_hr_user:
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n\n"
                f"Вы вошли как **HR-агент**\n\n"
                f"**Что я умею:**\n"
                f"• 📄 Парсить резюме — просто отправь PDF или DOCX\n"
                f"• 🔍 Искать кандидатов — напиши 'найди инженера-конструктора' или 'найди бухгалтера'\n"
                f"• 💼 Добавить вакансию — напиши 'добавить вакансию'\n"
                f"• 📝 Генерировать тестовые задания — напиши 'создай тест для production junior'\n"
                f"• 📋 План онбординга — напиши 'сделай онбординг для Ивана'\n"
                f"• 📊 NPS опросы — напиши 'создай nps опрос'\n"
                f"• 📈 Графики опросов — напиши 'график опроса 1' или 'pulse график 1'\n\n"
                f"**Управление кандидатами:**\n"
                f"• 'покажи кандидатов' — список всех (с кнопками листания)\n"
                f"• 'инфо кандидат 1' — полная информация\n"
                f"• 'редактировать кандидата 1' — редактирование\n"
                f"• 'удалить кандидата 1' — удалить\n"
                f"• 'удалить всех кандидатов' — удалить всех\n"
                f"• 'экспорт кандидата в pdf 1' — сохранить в PDF\n"
                f"• 'архивировать кандидата 1' — отправить в архив\n"
                f"• 'показать архив' — посмотреть архив\n"
                f"• 'восстановить из архива 1' — вернуть из архива\n\n"
                f"**Управление вакансиями:**\n"
                f"• 'покажи вакансии' — список всех (с кнопками листания)\n"
                f"• 'инфо вакансия 1' — полная информация\n"
                f"• 'редактировать вакансию 1' — редактирование\n"
                f"• 'удалить вакансию 1' — удалить\n"
                f"• 'удалить все вакансии' — удалить все\n"
                f"• 'экспорт вакансии в pdf 1' — сохранить в PDF\n\n"
                f"**Экспорт:**\n"
                f"• 'экспорт теста в pdf' — сохранить тест\n"
                f"• 'сохранить тест в pdf имя_файла.pdf' — сохранить с именем\n"
                f"• 'экспорт онбординга в pdf' — сохранить план\n"
                f"• 'редактировать тест' — изменить последний тест\n"
                f"• 'редактировать онбординг' — изменить план\n"
                f"• 'отмена' — прервать действие\n\n"
                f"**Управление собеседованиями:**\n"
                f"• 'управление собеседованиями' — управление слотами\n"
                f"• '/add_slot 2025-05-15 14:00' — добавить слот\n"
                f"• '/my_slots' — мои слоты\n"
                f"• '/del_slot 1' — удалить слот\n\n"
                f"**Оффер (приём на работу):**\n"
                f"• 'взять 26 на инженера с зп 80000' — отправить предложение\n\n"
                f"**Визуализация:**\n"
                f"• 'график опроса 1' — диаграмма NPS опроса\n"
                f"• 'pulse график 1' — динамика Pulse опроса\n\n"
                f"**Опросы:**\n"
                f"• 'покажи опросы' — список всех опросов (с кнопками листания)\n\n"
                f"**Поддерживаемые сферы деятельности:**\n"
                f"• IT и разработка • Производство • Строительство • Логистика •\n"
                f"• Офис и управление • Продажи • Маркетинг • Финансы • HR\n\n"
                f"**Используйте кнопки ниже!**\n\n"
                f"Поехали! 🚀",
                reply_markup=get_main_keyboard()
            )
        else:
            existing = HRAgentFacade.get_candidate_by_telegram_id(user_id)
            
            if existing and existing.get('status') == 'hired':
                await update.message.reply_text(
                    f"👋 С возвращением, {user.first_name}!\n\n"
                    f"Вы уже приняты на работу. Используйте меню онбординга ниже:",
                    reply_markup=get_onboarding_reply_keyboard()
                )
            else:
                await update.message.reply_text(
                    f"👋 Привет, {user.first_name}!\n\n"
                    f"Вы вошли как **соискатель**\n\n"
                    f"**Что вы можете сделать:**\n"
                    f"• 📄 Отправить резюме — просто отправьте файл PDF или DOCX\n\n"
                    f"Ваше резюме будет автоматически добавлено в базу кандидатов.\n"
                    f"HR свяжется с вами при наличии подходящих вакансий.\n\n"
                    f"📌 *Чтобы отправить резюме, просто отправьте файл в этот чат*",
                    reply_markup=get_candidate_keyboard()
                )
        
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")
        await update.message.reply_text("😕 Произошла ошибка. Попробуйте позже.")
