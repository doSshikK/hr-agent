"""Тестовые задания и онбординг"""

import re
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.services.test_generator import generate_test, format_test
from app.services.onboarding_generator import generate_onboarding_plan, format_onboarding_plan
from app.utils.export import export_test_to_pdf, export_onboarding_to_pdf
from .middlewares import get_role, is_hr

from .utils import extract_test_params, detect_direction_from_role, extract_name_from_text, validate_date, clear_user_state
from .keyboards import get_cancel_keyboard, get_main_keyboard
from .states import DEPARTMENT_MAP, DEPT_NAMES

logger = get_logger(__name__)

DIRECTION_NAMES = {
    "frontend": "Frontend",
    "backend": "Backend",
    "fullstack": "Fullstack",
    "devops": "DevOps",
    "mobile": "Mobile",
    "it": "IT и разработка",
    "production": "Производство",
    "construction": "Строительство",
    "logistics": "Логистика и склад",
    "office": "Офис и управление",
    "sales": "Продажи",
    "marketing": "Маркетинг и реклама",
    "finance": "Бухгалтерия и финансы",
    "hr": "HR и управление персоналом",
    "custom": "Другая сфера"
}

LEVEL_RU = {
    "junior": "Junior (начальный)",
    "middle": "Middle (средний)",
    "senior": "Senior (старший)"
}


def _get_user_state(context, user_id):
    """Получает состояние пользователя из context.user_data"""
    if context and hasattr(context, 'user_data'):
        return context.user_data.get("user_state", {})
    return {}


def _set_user_state(context, user_id, value):
    """Устанавливает состояние пользователя в context.user_data"""
    if context and hasattr(context, 'user_data'):
        context.user_data["user_state"] = value


def _get_temp_data(context, user_id):
    """Получает временные данные из context.user_data"""
    if context and hasattr(context, 'user_data'):
        return context.user_data.get("temp_data", {})
    return {}


def _set_temp_data(context, user_id, value):
    """Устанавливает временные данные в context.user_data"""
    if context and hasattr(context, 'user_data'):
        context.user_data["temp_data"] = value


async def handle_test_generation(update: Update, text: str):
    try:
        user_id = update.effective_user.id
        params = extract_test_params(text)
        
        if not params["direction"] and not params["level"] and not params["candidate_name"]:
            await update.message.reply_text(
                "🎯 **Создание тестового задания**\n\n"
                "Введите **должность** или **направление деятельности** кандидата:\n"
                "Например: frontend разработчик, инженер-конструктор, бухгалтер, менеджер по продажам\n\n"
                "📌 Поддерживаемые направления: IT, Производство, Строительство, Логистика, Офис, Продажи, Маркетинг, Финансы, HR",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if params["candidate_name"] and not params["direction"]:

            await update.message.reply_text(
                f"👤 Кандидат: {params['candidate_name']}\n\n"
                f"❌ **Не указано направление**\n"
                f"Напишите: IT, production, construction, logistics, office, sales, marketing, finance, hr\n"
                f"Или укажите должность (например, 'инженер-конструктор', 'бухгалтер', 'менеджер')",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if not params["direction"]:
            await update.message.reply_text(
                "🎯 **Создание тестового задания**\n\n"
                "Введите **должность** или **направление деятельности** кандидата:\n"
                "Например: frontend разработчик, инженер-конструктор, бухгалтер, менеджер по продажам",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if not params["level"]:
            params["level"] = "middle"
        
        status_msg = await update.message.reply_text(
            f"🔄 **Генерация тестового задания**\n\n"
            f"🎯 Направление: {params['direction']}\n"
            f"{f'👤 Кандидат: {params['candidate_name']}' if params.get('candidate_name') else ''}\n\n"
            f"⏳ Пожалуйста, подождите... (15-30 секунд)"
        )
        
        test = generate_test(
            direction=params["direction"], level=params["level"],
            tech_stack=params["tech_stack"], candidate_name=params["candidate_name"]
        )
        await status_msg.delete()
        
        if "error" in test:
            await update.message.reply_text(f"❌ Ошибка: {test['error']}")
        else:
            formatted = format_test(test)
            formatted += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            formatted += "\n📌 **Чтобы сохранить тест в PDF, напишите:**"
            formatted += "\n   • `экспорт теста в pdf`"
            formatted += "\n   • `сохранить тест в pdf имя_файла.pdf`"
            formatted += "\n\n✏️ **Чтобы отредактировать тест, напишите:**"
            formatted += "\n   • `редактировать тест`"
            formatted += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            await update.message.reply_text(formatted, parse_mode="Markdown", reply_markup=get_main_keyboard())

    except Exception as e:
        logger.error(f"Ошибка в handle_test_generation: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def export_test_pdf_command(update: Update, text: str, user_id: int):
    """Экспортирует тест в PDF и отправляет в чат (устарело — используйте handlers.py)"""

    await update.message.reply_text("❌ Используйте кнопки в интерфейсе для экспорта PDF")


async def handle_editing_test(update, text, user_id, state_obj):
    """Обрабатывает редактирование теста (устарело — используйте handlers.py)"""
    
    if text.lower() == "отмена":
        await update.message.reply_text("✅ Редактирование теста отменено", reply_markup=get_main_keyboard())
        return
    
    await update.message.reply_text("ℹ️ Редактирование теста теперь доступно через кнопки в интерфейсе.", reply_markup=get_main_keyboard())
    return True


async def handle_onboarding_start(update: Update, candidate_name: str = None, context=None):
    try:
        user_id = update.effective_user.id

        if candidate_name:
            _set_temp_data(context, user_id, {"name": candidate_name})
            _set_user_state(context, user_id, {"state": "onboarding_waiting_for_role", "name": candidate_name})
            await update.message.reply_text(
                f"👤 Сотрудник: {candidate_name}\n\n"
                f"🎯 Введите **должность** сотрудника:\n"
                f"Например: разработчик, инженер-конструктор, бухгалтер, менеджер, логист, маркетолог\n"
                f"❌ 'отмена' для отмены",
                reply_markup=get_cancel_keyboard()
            )
            return

        _set_user_state(context, user_id, {"state": "onboarding_waiting_for_name"})
        await update.message.reply_text(
            "📋 **Создание плана онбординга**\n\n"
            "Введите **имя** сотрудника:\n❌ 'отмена' для отмены",
            reply_markup=get_cancel_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в handle_onboarding_start: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_onboarding_role(update: Update, role_text: str, name: str, context=None):
    """Обрабатывает ввод должности для онбординга"""
    try:
        user_id = update.effective_user.id
        
        department = "development"
        lower_role = role_text.lower()
        for key, value in DEPARTMENT_MAP.items():
            if key in lower_role:
                department = value
                break
        
        dept_name = DEPT_NAMES.get(department, "Разработка")
        
        tech_departments = ["development", "analytics", "design"]
        if department in tech_departments:
            _set_user_state(context, user_id, {
                "state": "onboarding_waiting_for_level",
                "name": name, "department": department,
                "role_text": role_text, "dept_name": dept_name
            })
            await update.message.reply_text(
                f"👤 Сотрудник: {name}\n🎯 Должность: {role_text}\n🏢 Отдел: {dept_name}\n\n"
                f"📊 Выберите **уровень**: junior, middle или senior",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        _set_user_state(context, user_id, {
            "state": "onboarding_waiting_for_date",
            "name": name, "department": department, "level": None,
            "role_text": role_text, "dept_name": dept_name
        })
        await update.message.reply_text(
            f"👤 Сотрудник: {name}\n🎯 Должность: {role_text}\n🏢 Отдел: {dept_name}\n\n"
            f"📅 Введите **дату начала** (ДД.ММ.ГГГГ или ДД.ММ.ГГ)",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_onboarding_role: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_onboarding_level(update: Update, level_text: str, name: str, department: str, role_text: str, dept_name: str, context=None):
    """Обрабатывает ввод уровня для онбординга (для технических должностей)"""
    try:
        user_id = update.effective_user.id
        level = level_text.lower()
        
        if level not in ["junior", "middle", "senior"]:
            await update.message.reply_text("❌ Неверный уровень. Доступны: junior, middle, senior")
            return
        
        _set_user_state(context, user_id, {
            "state": "onboarding_waiting_for_date",
            "name": name, "department": department, "level": level,
            "role_text": role_text, "dept_name": dept_name
        })
        await update.message.reply_text(
            f"👤 Сотрудник: {name}\n🎯 Должность: {role_text}\n🏢 Отдел: {dept_name}\n"
            f"📊 Уровень: {LEVEL_RU.get(level, level.upper())}\n\n"
            f"📅 Введите **дату начала** (ДД.ММ.ГГГГ или ДД.ММ.ГГ)",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_onboarding_level: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_onboarding_date(update: Update, date_str: str, name: str, department: str, level: str, role_text: str, dept_name: str, context=None):
    """Обрабатывает ввод даты и генерирует план онбординга"""
    try:
        user_id = update.effective_user.id
        
        is_valid, date_obj, error_msg = validate_date(date_str)
        if not is_valid:
            await update.message.reply_text(f"❌ {error_msg}")
            return
        
        start_date = date_obj.strftime("%Y-%m-%d")
        
        candidate = {"id": None, "name": name, "email": None}
        plan = generate_onboarding_plan(
            candidate=candidate, department=department, level=level, start_date=start_date
        )
        
        temp_data_local = _get_temp_data(context, user_id)
        temp_data_local["last_onboarding"] = plan
        _set_temp_data(context, user_id, temp_data_local)
        plan["role_text"] = role_text
        plan["dept_name"] = dept_name
        
        output = [
            f"📋 **ПЛАН ОНБОРДИНГА ДЛЯ {name.upper()}**",
            f"🎯 Должность: {role_text}",
            f"🏢 Отдел: {dept_name}",
            f"📅 Дата начала: {plan.get('start_date_readable', '—')}",
            "", "**✅ ЧЕК-ЛИСТ ЗАДАЧ:**"
        ]
        for task in plan.get('checklist', [])[:7]:
            output.append(f"   • День {task['planned_day']} ({task['deadline_readable']}): {task['task']}")
        
        output.extend(["", "**📅 ПЛАН ВСТРЕЧ:**"])
        for meeting in plan.get('meetings', []):
            output.append(f"   • {meeting['date_readable']} {meeting['time']} — {meeting['with']}: {meeting['topic']}")
        
        if plan.get('recommendations'):
            output.extend(["", "**💡 РЕКОМЕНДАЦИИ:**"])
            output.extend([f"   • {rec}" for rec in plan['recommendations']])
        
        output.extend(["", "", "📌 *Чтобы сохранить план в PDF, напишите: экспорт онбординга в pdf*"])
        output.extend(["📌 *Чтобы редактировать план, напишите: редактировать онбординг*"])
        
        await update.message.reply_text("\n".join(output), parse_mode="Markdown", reply_markup=get_main_keyboard())
        
        _set_user_state(context, user_id, {})
        
    except Exception as e:
        logger.error(f"Ошибка в handle_onboarding_date: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def export_onboarding_pdf_command(update: Update, text: str, user_id: int):
    """Экспортирует план онбординга в PDF и отправляет в чат (устарело — используйте handlers.py)"""

    await update.message.reply_text("❌ Используйте кнопки в интерфейсе для экспорта PDF")


async def handle_editing_onboarding(update, text, user_id, state_obj):
    """Обрабатывает редактирование плана онбординга (устарело — используйте handlers.py)"""
    if text.lower() == "отмена":
        await update.message.reply_text("✅ Редактирование онбординга отменено", reply_markup=get_main_keyboard())

        return
    
    await update.message.reply_text("ℹ️ Редактирование онбординга теперь доступно через кнопки в интерфейсе.", reply_markup=get_main_keyboard())
    return True
