"""Обработка документов (резюме) и ответов после парсинга"""

import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.utils.file_parser import parse_resume
from app.core.config import settings
from app.services.hr_facade import HRAgentFacade
from .middlewares import get_role, is_hr

from .utils import clear_user_state
from .keyboards import get_candidate_keyboard, get_main_keyboard

logger = get_logger(__name__)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик загруженных документов (резюме)"""
    try:
        user_id = update.effective_user.id
        document = update.message.document
        
        file_name = document.file_name or ""
        file_ext = Path(file_name).suffix.lower()
        
        if file_ext not in ['.pdf', '.docx']:
            await update.message.reply_text("❌ Только PDF и DOCX")
            return
        
        user_role = get_role(context) if hasattr(context, 'user_data') else None
        is_hr_user = user_role == "hr" if user_role else settings.is_hr(user_id)
        
        if not is_hr_user:
            existing = HRAgentFacade.get_candidate_by_telegram_id(user_id)
            if not existing:
                HRAgentFacade.save_candidate({
                    "telegram_id": user_id,
                    "name": update.effective_user.first_name,
                    "source": "telegram"
                }, None)
                logger.info(f"✅ Зарегистрирован кандидат {user_id}")
            else:
                logger.info(f"✅ Кандидат {user_id} уже зарегистрирован")
            
            await update.message.reply_text(f"📄 Получил {file_name}\n🔄 Сохраняю резюме...")
            
            file = await document.get_file()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name
            
            parsed_data = parse_resume(tmp_path)
            
            if "error" in parsed_data:
                await update.message.reply_text(f"❌ Ошибка: {parsed_data['error']}")
                os.unlink(tmp_path)
                return
            
            parsed_data['telegram_id'] = user_id
            
            parsed_data['source'] = 'telegram'
            
            candidate_id = HRAgentFacade.save_candidate(parsed_data, tmp_path)
            
            try:
                candidate_name = parsed_data.get('name', 'Не указано')
                last_position = parsed_data.get('last_position', '')
                
                if not HRAgentFacade.is_candidate_in_notification_queue(candidate_id):
                    HRAgentFacade.add_to_notification_queue(candidate_id, candidate_name, last_position)
                    logger.info(f"✅ Кандидат {candidate_id} добавлен в очередь уведомлений")
                else:
                    logger.info(f"⏭️ Кандидат {candidate_id} уже есть в очереди, пропускаем")
            except Exception as e:
                logger.error(f"Ошибка добавления в очередь уведомлений: {e}")
            
            os.unlink(tmp_path)
            
            await update.message.reply_text(
                "✅ **Спасибо! Ваше резюме принято.**\n\n"
                "Мы рассмотрим его и свяжемся с вами при наличии подходящих вакансий.\n\n"
                "Хорошего дня! 🙌",
                reply_markup=get_candidate_keyboard()
            )
            return
        
        await update.message.reply_text(f"📄 Получил {file_name}\n🔄 Парсинг...")
        
        file = await document.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name
        
        parsed_data = parse_resume(tmp_path)
        
        if "error" in parsed_data:
            await update.message.reply_text(f"❌ Ошибка парсинга: {parsed_data['error']}")
            os.unlink(tmp_path)
            return
        
        email = parsed_data.get("email")
        name = parsed_data.get("name")
        exists = False
        existing = None
        
        candidates = HRAgentFacade.get_all_candidates(limit=1000)
        if email:
            for c in candidates:
                if c.get("email") and c.get("email").lower() == email.lower():
                    exists = True
                    existing = c
                    break
        if not exists and name:
            for c in candidates:
                if c.get("name") and c.get("name").lower() == name.lower():
                    exists = True
                    existing = c
                    break
        
        output = []
        output.append("📄 **РЕЗУЛЬТАТ ПАРСИНГА РЕЗЮМЕ**")
        output.append("=" * 50)
        output.append("")
        output.append("👤 **Личные данные:**")
        output.append(f"   • Имя: {parsed_data.get('name', '—')}")
        output.append(f"   • Email: {parsed_data.get('email', '—')}")
        output.append(f"   • Телефон: {parsed_data.get('phone', '—')}")
        output.append("")
        output.append("💼 **Опыт работы:**")
        output.append(f"   • Общий опыт: {parsed_data.get('experience_years', 0)} лет")
        output.append(f"   • Последняя должность: {parsed_data.get('last_position', '—')}")
        output.append(f"   • Последняя компания: {parsed_data.get('last_company', '—')}")
        output.append("")
        output.append("🛠️ **Навыки:**")
        skills = parsed_data.get('skills', [])
        if skills:
            output.append(f"   • {', '.join(skills[:15])}")
            if len(skills) > 15:
                output.append(f"   • ... и ещё {len(skills) - 15} навыков")
        else:
            output.append("   • Навыки не найдены")
        output.append("")
        output.append("=" * 50)
        output.append("")
        
        if exists:
            output.append(f"⚠️ **КАНДИДАТ УЖЕ ЕСТЬ В БАЗЕ!**")
            output.append(f"   • ID: {existing.get('id')}")
            output.append(f"   • Имя: {existing.get('name')}")
            output.append(f"   • Email: {existing.get('email')}")
            output.append("")
            output.append("📌 **Что делать?**")
            output.append("   • Напишите 'обновить' — обновить данные кандидата")
            output.append("   • Напишите 'нет' — пропустить")
        else:
            output.append(f"✅ **КАНДИДАТ НЕ НАЙДЕН В БАЗЕ**")
            output.append("")
            output.append("📌 **Что делать?**")
            output.append("   • Напишите 'да' или 'добавить' — сохранить кандидата в базу")
            output.append("   • Напишите 'нет' — пропустить")
        
        temp_data_local = context.user_data.get("temp_data", {})
        temp_data_local["parsed_candidate"] = parsed_data
        temp_data_local["file_path"] = tmp_path
        context.user_data["temp_data"] = temp_data_local
        
        await update.message.reply_text("\n".join(output), reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"Ошибка в handle_document: {e}")
        await update.message.reply_text(f"❌ Не удалось обработать файл: {str(e)}")
