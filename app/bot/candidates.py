"""Всё о кандидатах и вакансиях"""

import re
from datetime import datetime
from pathlib import Path
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.services.hr_facade import HRAgentFacade
from app.utils.export import export_candidate_to_pdf, export_job_to_pdf
from .middlewares import get_role, is_hr

from .utils import format_years, clear_user_state
from .keyboards import get_main_keyboard, get_cancel_keyboard

logger = get_logger(__name__)


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


async def handle_candidate_addition(user_id, text, update, context=None):
    state = _get_user_state(context, user_id)
    if isinstance(state, dict):
        state = state.get("state", "")
    
    if state == "waiting_for_name":
        _set_temp_data(context, user_id, {"name": text})
        _set_user_state(context, user_id, {"state": "waiting_for_email"})
        await update.message.reply_text(f"✅ Имя: {text}\n\n📧 Введите **email** (или '-')", reply_markup=get_cancel_keyboard())
    
    elif state == "waiting_for_email":
        email = None if text == "-" else text
        temp = _get_temp_data(context, user_id)
        temp["email"] = email
        _set_temp_data(context, user_id, temp)
        _set_user_state(context, user_id, {"state": "waiting_for_phone"})
        await update.message.reply_text(f"✅ Email: {email if email else 'пропущен'}\n\n📞 Введите **телефон** (только цифры, или '-')", reply_markup=get_cancel_keyboard())
    
    elif state == "waiting_for_phone":
        if text != "-":
            cleaned = re.sub(r'[^\d]', '', text)
            if not cleaned:
                await update.message.reply_text("❌ Телефон должен содержать только цифры. Попробуйте ещё раз (или '-' чтобы пропустить):", reply_markup=get_cancel_keyboard())
                return
            phone = cleaned
        else:
            phone = None
        temp = _get_temp_data(context, user_id)
        temp["phone"] = phone
        _set_temp_data(context, user_id, temp)
        _set_user_state(context, user_id, {"state": "waiting_for_experience"})
        await update.message.reply_text(f"✅ Телефон: {phone if phone else 'пропущен'}\n\n💼 Введите **опыт** (только число лет, цифрами)", reply_markup=get_cancel_keyboard())
    
    elif state == "waiting_for_experience":
        if not text.isdigit():
            await update.message.reply_text("❌ Опыт должен быть числом (количество лет). Попробуйте ещё раз:", reply_markup=get_cancel_keyboard())
            return
        experience = int(text)
        temp = _get_temp_data(context, user_id)
        temp["experience"] = experience
        _set_temp_data(context, user_id, temp)
        _set_user_state(context, user_id, {"state": "waiting_for_position"})
        await update.message.reply_text(f"✅ Опыт: {experience} лет\n\n📋 Введите **последнюю должность** (или '-')", reply_markup=get_cancel_keyboard())
    
    elif state == "waiting_for_position":
        position = None if text == "-" else text
        temp = _get_temp_data(context, user_id)
        temp["position"] = position
        _set_temp_data(context, user_id, temp)
        _set_user_state(context, user_id, {"state": "waiting_for_company"})
        await update.message.reply_text(f"✅ Должность: {position if position else 'пропущена'}\n\n🏢 Введите **компанию** (или '-')", reply_markup=get_cancel_keyboard())
    
    elif state == "waiting_for_company":
        company = None if text == "-" else text
        temp = _get_temp_data(context, user_id)
        temp["company"] = company
        _set_temp_data(context, user_id, temp)
        _set_user_state(context, user_id, {"state": "waiting_for_skills"})
        await update.message.reply_text(f"✅ Компания: {company if company else 'пропущена'}\n\n🛠️ Введите **навыки** через запятую (или '-')", reply_markup=get_cancel_keyboard())
    
    elif state == "waiting_for_skills":
        skills = [] if text == "-" else [s.strip() for s in text.split(",")]
        data = _get_temp_data(context, user_id)
        
        email = data.get("email")
        if email:
            existing_candidates = HRAgentFacade.get_all_candidates(limit=1000)
            for c in existing_candidates:
                if c.get("email") and c.get("email").lower() == email.lower():
                    await update.message.reply_text("⚠️ Кандидат с таким email уже есть! Напишите 'отмена'", reply_markup=get_cancel_keyboard())
                    _set_user_state(context, user_id, {})
                    _set_temp_data(context, user_id, {})
                    return
        
        candidate_data = {
            "name": data.get("name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "experience_years": data.get("experience", 0),
            "last_position": data.get("position"),
            "last_company": data.get("company"),
            "skills": skills
        }
        
        candidate_id = HRAgentFacade.save_candidate(candidate_data, None)
        
        await update.message.reply_text(f"✅ **КАНДИДАТ ДОБАВЛЕН!** ID: {candidate_id}", reply_markup=get_main_keyboard())
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})


async def handle_job_addition(user_id, text, update, context=None):
    try:
        state = context.user_data.get("user_state")
        
        skip = text == "-"
        
        if state == "job_waiting_for_title":
            context.user_data["temp_data"] = {"job_title": text}
            context.user_data["user_state"] = "job_waiting_for_level"
            await update.message.reply_text(
                f"✅ Название: {text}\n\n"
                f"📊 Введите **уровень** (junior/middle/senior) или '-' для пропуска",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if state == "job_waiting_for_level":
            level = None if skip else text.lower()
            if level and level not in ["junior", "middle", "senior"]:
                await update.message.reply_text("❌ Уровень должен быть: junior, middle или senior", reply_markup=get_cancel_keyboard())
                return
            
            temp = context.user_data.get("temp_data", {})
            temp["job_level"] = level
            context.user_data["temp_data"] = temp
            context.user_data["user_state"] = "job_waiting_for_skills"
            await update.message.reply_text(
                f"✅ Уровень: {level if level else 'пропущен'}\n\n"
                f"🛠️ Введите **навыки** через запятую или '-' для пропуска",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if state == "job_waiting_for_skills":
            skills = [] if skip else [s.strip() for s in text.split(",")]
            temp = context.user_data.get("temp_data", {})
            temp["job_skills"] = skills
            context.user_data["temp_data"] = temp
            context.user_data["user_state"] = "job_waiting_for_experience"
            await update.message.reply_text(
                f"✅ Навыки: {', '.join(skills[:5]) if skills else 'не указаны'}\n\n"
                f"💼 Введите **требуемый опыт** (цифрой)",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if state == "job_waiting_for_experience":
            experience = int(text) if text.isdigit() else 0
            temp = context.user_data.get("temp_data", {})
            temp["job_experience"] = experience
            context.user_data["temp_data"] = temp
            context.user_data["user_state"] = "job_waiting_for_description"
            await update.message.reply_text(
                f"✅ Опыт: {experience} лет\n\n"
                f"📝 Введите **описание** или '-' для пропуска",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        if state == "job_waiting_for_description":
            description = None if skip else text
            data = context.user_data.get("temp_data", {})
            
            job_id = HRAgentFacade.create_job({
                "title": data.get("job_title"),
                "level": data.get("job_level") or "middle",
                "skills": data.get("job_skills", []),
                "experience": data.get("job_experience", 0),
                "description": description or ""
            })
            
            context.user_data["user_state"] = {}
            context.user_data["temp_data"] = {}
            
            await update.message.reply_text(
                f"✅ **ВАКАНСИЯ ДОБАВЛЕНА!** ID: {job_id}",
                reply_markup=get_main_keyboard()
            )
            return
            
    except Exception as e:
        logger.error(f"Ошибка в handle_job_addition: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        context.user_data["user_state"] = {}
        context.user_data["temp_data"] = {}


async def handle_editing_candidate(update, text, user_id, state_obj, context=None):
    data = _get_temp_data(context, user_id)
    step = data.get("edit_step")
    candidate_id = data.get("edit_candidate_id")
    candidate = HRAgentFacade.get_candidate(candidate_id)
    
    if not candidate:
        await update.message.reply_text("❌ Кандидат не найден")
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
        return
    
    if step == "name":
        new_value = None if text == "-" else text
        data["new_name"] = new_value
        data["edit_step"] = "email"
        await update.message.reply_text(
            f"✅ Имя: {new_value if new_value else 'оставлено без изменений'}\n\n"
            f"Текущий email: {candidate.get('email', '—')}\n\n"
            f"Введите **новый email** (или '-' чтобы пропустить, 'отмена' для отмены)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "email":
        new_value = None if text == "-" else text
        data["new_email"] = new_value
        data["edit_step"] = "phone"
        await update.message.reply_text(
            f"✅ Email: {new_value if new_value else 'оставлен без изменений'}\n\n"
            f"Текущий телефон: {candidate.get('phone', '—')}\n\n"
            f"Введите **новый телефон** (или '-' чтобы пропустить, 'отмена' для отмены)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "phone":
        new_value = None if text == "-" else text
        data["new_phone"] = new_value
        data["edit_step"] = "experience"
        await update.message.reply_text(
            f"✅ Телефон: {new_value if new_value else 'оставлен без изменений'}\n\n"
            f"Текущий опыт: {candidate.get('experience_years', 0)} лет\n\n"
            f"Введите **новый опыт** (цифрой, или '-' чтобы пропустить, 'отмена' для отмены)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "experience":
        new_value = int(text) if text.isdigit() else None
        if text != "-" and new_value is None:
            await update.message.reply_text("❌ Введите число или '-'", reply_markup=get_cancel_keyboard())
            return
        data["new_experience"] = new_value
        data["edit_step"] = "position"
        
        exp_text = format_years(new_value) if new_value else "оставлен без изменений"
        await update.message.reply_text(
            f"✅ Опыт: {exp_text}\n\n"
            f"Текущая должность: {candidate.get('last_position', '—')}\n\n"
            f"Введите **новую должность** (или '-' чтобы пропустить, 'отмена' для отмены)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "position":
        new_value = None if text == "-" else text
        data["new_position"] = new_value
        data["edit_step"] = "skills"
        await update.message.reply_text(
            f"✅ Должность: {new_value if new_value else 'оставлена без изменений'}\n\n"
            f"Текущие навыки: {', '.join(candidate.get('skills', []))}\n\n"
            f"Введите **новые навыки** через запятую (или '-' чтобы пропустить, 'отмена' для отмены)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "skills":
        new_value = [] if text == "-" else [s.strip() for s in text.split(",")]
        data["new_skills"] = new_value
        
        updates = {}
        if data.get("new_name"):
            updates["name"] = data["new_name"]
        if data.get("new_email"):
            updates["email"] = data["new_email"]
        if data.get("new_phone"):
            updates["phone"] = data["new_phone"]
        if data.get("new_experience") is not None:
            updates["experience_years"] = data["new_experience"]
        if data.get("new_position"):
            updates["last_position"] = data["new_position"]
        if data.get("new_skills"):
            updates["skills"] = data["new_skills"]
        
        if updates:
            from app.services.candidate_service import update_candidate
            if update_candidate(candidate_id, updates):
                await update.message.reply_text(f"✅ Кандидат #{candidate_id} успешно обновлён!", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text(f"❌ Ошибка при обновлении кандидата")
        else:
            await update.message.reply_text(f"ℹ️ Изменений не внесено")
        
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    
    _set_temp_data(context, user_id, data)
    return True


async def handle_editing_job(update, text, user_id, state_obj, context=None):
    data = _get_temp_data(context, user_id)
    step = data.get("edit_step")
    job_id = data.get("edit_job_id")
    job = HRAgentFacade.get_job(job_id)
    
    if not job:
        await update.message.reply_text("❌ Вакансия не найдена")
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
        return
    
    if step == "title":
        new_value = None if text == "-" else text
        data["new_title"] = new_value
        data["edit_step"] = "level"
        await update.message.reply_text(
            f"✅ Название: {new_value if new_value else 'оставлено без изменений'}\n\n"
            f"Текущий уровень: {job.get('level', 'middle')}\n\n"
            f"Введите **новый уровень** (junior/middle/senior, или '-' чтобы пропустить)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "level":
        new_value = None if text == "-" else text.lower()
        if new_value and new_value not in ["junior", "middle", "senior"]:
            await update.message.reply_text("❌ Уровень должен быть: junior, middle или senior", reply_markup=get_cancel_keyboard())
            return
        data["new_level"] = new_value
        data["edit_step"] = "experience"
        await update.message.reply_text(
            f"✅ Уровень: {new_value if new_value else 'оставлен без изменений'}\n\n"
            f"Текущий требуемый опыт: {job.get('experience', 0)} лет\n\n"
            f"Введите **новый опыт** (цифрой, или '-' чтобы пропустить)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "experience":
        new_value = int(text) if text.isdigit() else None
        if text != "-" and new_value is None:
            await update.message.reply_text("❌ Введите число или '-'", reply_markup=get_cancel_keyboard())
            return
        data["new_experience"] = new_value
        data["edit_step"] = "skills"
        await update.message.reply_text(
            f"✅ Опыт: {new_value if new_value else 'оставлен без изменений'} лет\n\n"
            f"Текущие навыки: {', '.join(job.get('skills', []))}\n\n"
            f"Введите **новые навыки** через запятую (или '-' чтобы пропустить)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "skills":
        new_value = [] if text == "-" else [s.strip() for s in text.split(",")]
        data["new_skills"] = new_value
        data["edit_step"] = "description"
        await update.message.reply_text(
            f"✅ Навыки: {', '.join(new_value) if new_value else 'оставлены без изменений'}\n\n"
            f"Текущее описание: {job.get('description', '—')[:100]}...\n\n"
            f"Введите **новое описание** (или '-' чтобы пропустить)",
            reply_markup=get_cancel_keyboard()
        )
    elif step == "description":
        new_value = None if text == "-" else text
        data["new_description"] = new_value
        
        updates = {}
        if data.get("new_title"):
            updates["title"] = data["new_title"]
        if data.get("new_level"):
            updates["level"] = data["new_level"]
        if data.get("new_experience") is not None:
            updates["experience"] = data["new_experience"]
        if data.get("new_skills") is not None:
            updates["skills"] = data["new_skills"]
        if data.get("new_description") is not None:
            updates["description"] = data["new_description"]
        
        if updates:
            if HRAgentFacade.update_job_fields(job_id, **updates):
                await update.message.reply_text(f"✅ Вакансия #{job_id} успешно обновлена!", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text(f"❌ Ошибка при обновлении вакансии")
        else:
            await update.message.reply_text(f"ℹ️ Изменений не внесено")
        
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    
    _set_temp_data(context, user_id, data)
    return True


async def show_candidate_info(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        candidate_id = int(numbers[0])
        candidate = HRAgentFacade.get_candidate(candidate_id)
        if candidate:
            output = []
            output.append(f"👤 **{candidate.get('name', 'Без имени')}**")
            output.append(f"📧 Email: {candidate.get('email', '—')}")
            output.append(f"📞 Телефон: {candidate.get('phone', '—')}")
            output.append(f"💼 Опыт: {format_years(candidate.get('experience_years', 0))}")
            output.append(f"📋 Последняя должность: {candidate.get('last_position', '—')}")
            output.append(f"🏢 Последняя компания: {candidate.get('last_company', '—')}")
            output.append(f"🛠️ Навыки: {', '.join(candidate.get('skills', []))}")
            output.append(f"📅 Создан: {candidate.get('created_at', '—')}")
            output.append("")
            output.append("📌 *Чтобы экспортировать в PDF, напишите:*")
            output.append(f"   экспорт кандидата в pdf {candidate_id}")
            
            await update.message.reply_text("\n".join(output), reply_markup=get_main_keyboard())
            
            resume_data = HRAgentFacade.get_resume_from_db(candidate_id)
            if resume_data:
                resume_bytes, content_type, filename = resume_data
                await update.message.reply_document(
                    document=BytesIO(resume_bytes),
                    filename=filename,
                    caption="📄 **Резюме кандидата**"
                )
            else:
                await update.message.reply_text("📭 Резюме не найдено в базе данных")
        else:
            await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
    else:
        await update.message.reply_text("❌ Укажите ID. Пример: 'инфо кандидат 1'")


async def show_job_info(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        job_id = int(numbers[0])
        job = HRAgentFacade.get_job(job_id)
        if job:
            output = []
            output.append(f"💼 **{job.get('title', '—')}**")
            output.append(f"📊 Уровень: {job.get('level', '—')}")
            output.append(f"💼 Требуемый опыт: {job.get('experience', 0)} лет")
            output.append(f"🛠️ Навыки: {', '.join(job.get('skills', []))}")
            output.append(f"📝 Описание: {job.get('description', '—')}")
            output.append(f"📅 Создана: {job.get('created_at', '—')}")
            output.append(f"📌 Статус: {job.get('status', '—')}")
            output.append("")
            output.append("📌 *Чтобы экспортировать в PDF, напишите:*")
            output.append(f"   экспорт вакансии в pdf {job_id}")
            await update.message.reply_text("\n".join(output), reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
    else:
        await update.message.reply_text("❌ Укажите ID. Пример: 'инфо вакансия 1'")


async def show_candidates_list(update, context=None):
    candidates = HRAgentFacade.get_all_candidates(limit=1000)
    if not candidates:
        await update.message.reply_text("📭 Кандидатов пока нет", reply_markup=get_main_keyboard())
        return
    
    if context:
        context.user_data["pagination_candidates"] = {
            "items": candidates,
            "page_size": 10,
            "title": "СПИСОК КАНДИДАТОВ"
        }
    
    page_size = 10
    total_pages = (len(candidates) + page_size - 1) // page_size
    page_candidates = candidates[:page_size]
    
    output = [f"📋 **СПИСОК КАНДИДАТОВ** (страница 1/{total_pages})\n"]
    for cand in page_candidates:
        position = cand.get('last_position', 'Должность не указана')
        experience = format_years(cand.get('experience_years', 0))
        
        output.append(f"**#{cand.get('id')}** — {cand.get('name', 'Без имени')}")
        output.append(f"   • {position} | Опыт: {experience}")
    
    output.append(f"\n💡 Всего кандидатов: {len(candidates)}")
    
    keyboard = []
    if total_pages > 1:
        keyboard.append(InlineKeyboardButton("Вперед ▶️", callback_data="page_candidates_next_1"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    await update.message.reply_text("\n".join(output), reply_markup=reply_markup)


async def show_jobs_list(update, context=None):
    jobs = HRAgentFacade.get_all_jobs(active_only=False)
    if not jobs:
        await update.message.reply_text("📭 Вакансий пока нет", reply_markup=get_main_keyboard())
        return
    
    if context:
        context.user_data["pagination_jobs"] = {
            "items": jobs,
            "page_size": 10,
            "title": "СПИСОК ВАКАНСИЙ"
        }
    
    page_size = 10
    total_pages = (len(jobs) + page_size - 1) // page_size
    page_jobs = jobs[:page_size]
    
    output = [f"💼 **СПИСОК ВАКАНСИЙ** (страница 1/{total_pages})\n"]
    for job in page_jobs:
        status_icon = "✅" if job.get('status') == 'active' else "📦"
        level_icon = "🟢" if job.get('level') == 'junior' else "🟡" if job.get('level') == 'middle' else "🔴"
        output.append(f"{status_icon} {level_icon} **#{job.get('id')}** — {job.get('title', '—')} ({job.get('level', '—')})")
        if job.get('skills'):
            output.append(f"   • Навыки: {', '.join(job.get('skills', [])[:4])}")
    
    output.append(f"\n💡 Всего вакансий: {len(jobs)}")
    
    keyboard = []
    if total_pages > 1:
        keyboard.append(InlineKeyboardButton("Вперед ▶️", callback_data="page_jobs_next_1"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    await update.message.reply_text("\n".join(output), reply_markup=reply_markup)


async def export_candidate_to_pdf_command(update, text, user_id):
    numbers = re.findall(r'\d+', text)
    if numbers:
        candidate_id = int(numbers[0])
        candidate = HRAgentFacade.get_candidate(candidate_id)
        if candidate:
            filename = export_candidate_to_pdf(candidate)
            if filename:
                await update.message.reply_text(f"✅ Карточка кандидата сохранена в файл `{filename}`")
            else:
                await update.message.reply_text("❌ Ошибка при создании PDF")
        else:
            await update.message.reply_text(f"❌ Кандидат с ID {candidate_id} не найден")
    else:
        await update.message.reply_text("❌ Укажите ID. Пример: 'экспорт кандидата в pdf 1'")


async def export_job_to_pdf_command(update, text, user_id):
    numbers = re.findall(r'\d+', text)
    if numbers:
        job_id = int(numbers[0])
        job = HRAgentFacade.get_job(job_id)
        if job:
            filename = export_job_to_pdf(job)
            if filename:
                await update.message.reply_text(f"✅ Карточка вакансии сохранена в файл `{filename}`")
            else:
                await update.message.reply_text("❌ Ошибка при создании PDF")
        else:
            await update.message.reply_text(f"❌ Вакансия с ID {job_id} не найдена")
    else:
        await update.message.reply_text("❌ Укажите ID. Пример: 'экспорт вакансии в pdf 1'")


async def confirm_delete_candidate(update, text, user_id, state_obj, context=None):
    if text.lower() == "да":
        candidate_id = state_obj.get("candidate_id")
        name = state_obj.get("name")
        if HRAgentFacade.delete_candidate(candidate_id):
            await update.message.reply_text(f"✅ Кандидат **{name}** удалён", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Не удалось удалить")
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    elif text.lower() in ["отмена", "нет"]:
        await update.message.reply_text("❌ Удаление отменено.", reply_markup=get_main_keyboard())
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    else:
        await update.message.reply_text("❌ Напишите **ДА** для подтверждения или **отмена** для отмены.", reply_markup=get_cancel_keyboard())
    return True


async def confirm_delete_all_candidates(update, text, user_id, context=None):
    if text.lower() == "да":
        candidates = HRAgentFacade.get_all_candidates(limit=10000)
        for cand in candidates:
            HRAgentFacade.delete_candidate(cand["id"])
        await update.message.reply_text("✅ **ВСЕ КАНДИДАТЫ УДАЛЕНЫ!**", reply_markup=get_main_keyboard())
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    elif text.lower() in ["отмена", "нет"]:
        await update.message.reply_text("❌ Удаление отменено.", reply_markup=get_main_keyboard())
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    else:
        await update.message.reply_text("❌ Напишите **ДА** для подтверждения или **отмена** для отмены.", reply_markup=get_cancel_keyboard())
    return True


async def confirm_delete_all_jobs(update, text, user_id, context=None):
    if text.lower() == "да":
        jobs = HRAgentFacade.get_all_jobs(active_only=False)
        for job in jobs:
            HRAgentFacade.delete_job(job["id"])
        await update.message.reply_text("✅ **ВСЕ ВАКАНСИИ УДАЛЕНЫ!**", reply_markup=get_main_keyboard())
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    elif text.lower() in ["отмена", "нет"]:
        await update.message.reply_text("❌ Удаление отменено.", reply_markup=get_main_keyboard())
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    else:
        await update.message.reply_text("❌ Напишите **ДА** для подтверждения или **отмена** для отмены.", reply_markup=get_cancel_keyboard())
    return True
