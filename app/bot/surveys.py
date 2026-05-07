"""Всё об опросах (создание, анализ, графики)"""

import os
import re
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from app.services.hr_facade import HRAgentFacade
from .middlewares import get_role, is_hr

from .utils import clear_user_state

logger = get_logger(__name__)


def _get_user_state(context, user_id):
    if context and hasattr(context, 'user_data'):
        return context.user_data.get("user_state", {})
    return {}


def _set_user_state(context, user_id, value):
    if context and hasattr(context, 'user_data'):
        context.user_data["user_state"] = value


def _get_temp_data(context, user_id):
    if context and hasattr(context, 'user_data'):
        return context.user_data.get("temp_data", {})
    return {}


def _set_temp_data(context, user_id, value):
    if context and hasattr(context, 'user_data'):
        context.user_data["temp_data"] = value


async def create_survey_command(update, context, text):
    if "pulse" in text.lower():
        survey_type = "pulse"
        type_name = "Pulse"
    else:
        survey_type = "nps"
        type_name = "NPS"
    
    department = None
    dept_match = re.search(r'(?:для|отдела)\s+([А-Яа-яЁё\s]+)', text.lower())
    if dept_match:
        department = dept_match.group(1).strip()
    
    title = f"{type_name} опрос"
    if department:
        title += f" для {department}"
    title += f" от {datetime.now().strftime('%d.%m.%Y')}"
    
    try:
        survey_id = HRAgentFacade.create_survey(title, survey_type, department)
        
        questions = (
            "1. Насколько вероятно, что вы порекомендуете компанию? (0-10)\n2. Что можно улучшить?"
            if survey_type == "nps" else
            "1. Удовлетворенность работой (1-5)\n2. Уровень энергии (1-5)\n3. Ваш фидбек"
        )
        
        bot_username = (await context.bot.get_me()).username
        survey_link = f"https://t.me/{bot_username}?start=survey_{survey_id}"
        
        await update.message.reply_text(
            f"✅ **ОПРОС СОЗДАН!**\n\n"
            f"• ID: {survey_id}\n"
            f"• Тип: {type_name}\n"
            f"• Название: {title}\n"
            f"{f'• Отдел: {department}' if department else ''}\n\n"
            f"**Вопросы:**\n{questions}\n\n"
            f"🔗 **Ссылка для прохождения опроса:**\n{survey_link}\n\n"
            f"💡 Отправьте эту ссылку сотрудникам\n"
            f"💡 Для анализа результатов напишите 'проанализируй опрос {survey_id}'"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def analyze_survey_command(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        survey_id = int(numbers[0])
        result = HRAgentFacade.analyze_survey(survey_id)
        
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
            return
        
        output = [f"📊 **РЕЗУЛЬТАТЫ ОПРОСА #{survey_id}**"]
        output.append(f"📋 Всего ответов: {result.get('total_responses', 0)}")
        
        if result.get('survey_type') == 'nps':
            nps = result.get('nps_score', 0)
            if nps >= 70:
                grade = "🏆 Отлично!"
            elif nps >= 50:
                grade = "📊 Хорошо"
            elif nps >= 30:
                grade = "⚠️ Средне"
            else:
                grade = "🔴 Требует внимания"
            
            output.append(f"🎯 **NPS Score:** {nps} ({grade})")
            output.append(f"🟢 Промоутеры (9-10): {result.get('promoters', 0)}")
            output.append(f"🟡 Нейтралы (7-8): {result.get('passives', 0)}")
            output.append(f"🔴 Критики (0-6): {result.get('detractors', 0)}")
        
        elif result.get('survey_type') == 'pulse':
            output.append("📊 **Результаты Pulse опроса:**")
            if result.get('satisfaction'):
                output.append(f"😊 Удовлетворённость: {result['satisfaction'].get('average', 0):.1f}/5 (среднее)")
                output.append(f"   • Минимум: {result['satisfaction'].get('min', 0)}")
                output.append(f"   • Максимум: {result['satisfaction'].get('max', 0)}")
            if result.get('energy'):
                output.append(f"⚡ Энергия: {result['energy'].get('average', 0):.1f}/5 (среднее)")
                output.append(f"   • Минимум: {result['energy'].get('min', 0)}")
                output.append(f"   • Максимум: {result['energy'].get('max', 0)}")
        
        if result.get('feedbacks'):
            output.append("\n💬 **Последние отзывы:**")
            for fb in result['feedbacks'][:3]:
                output.append(f"   • {fb[:100]}")
        
        await update.message.reply_text("\n".join(output))
    else:
        await update.message.reply_text("❌ Укажите ID опроса. Пример: 'проанализируй опрос 1'")


async def show_surveys_list(update, context=None):
    surveys = HRAgentFacade.get_all_surveys(active_only=False)
    if not surveys:
        await update.message.reply_text("📭 Опросов пока нет")
        return
    
    if context:
        context.user_data["pagination_surveys"] = {
            "items": surveys,
            "page_size": 10,
            "title": "СПИСОК ОПРОСОВ"
        }
    
    page_size = 10
    total_pages = (len(surveys) + page_size - 1) // page_size
    page_surveys = surveys[:page_size]
    
    output = [f"📋 **СПИСОК ОПРОСОВ** (страница 1/{total_pages})\n"]
    for s in page_surveys:
        status_icon = "✅" if s.get('status') == 'active' else "📦"
        output.append(f"{status_icon} **#{s.get('id')}** — {s.get('title', '—')} ({s.get('type', '—')})")
    
    output.append(f"\n💡 Всего опросов: {len(surveys)}")
    
    keyboard = []
    if total_pages > 1:
        keyboard.append(InlineKeyboardButton("Вперед ▶️", callback_data="page_surveys_next_1"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    await update.message.reply_text("\n".join(output), reply_markup=reply_markup)


async def delete_survey_command(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        survey_id = int(numbers[0])
        
        survey = HRAgentFacade.get_survey(survey_id)
        if not survey:
            await update.message.reply_text(f"❌ Опрос с ID {survey_id} не найден")
            return
        
        HRAgentFacade.delete_survey(survey_id)
        
        await update.message.reply_text(
            f"✅ **ОПРОС УДАЛЁН!**\n\n"
            f"• ID: {survey_id}\n"
            f"• Название: {survey.get('title', '—')}\n\n"
            f"Опрос и все ответы на него удалены."
        )
    else:
        await update.message.reply_text(
            "❌ Укажите ID опроса для удаления.\n"
            "Пример: `удалить опрос 1`\n\n"
            "Чтобы увидеть ID, напишите 'покажи опросы'"
        )


async def chart_command(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        survey_id = int(numbers[0])
        await update.message.reply_text("📊 Строю график... Подождите секунду.")
        
        survey = HRAgentFacade.get_survey(survey_id)
        if not survey:
            await update.message.reply_text(f"❌ Опрос с ID {survey_id} не найден")
            return
        
        survey_type = survey.get('type', 'nps')
        
        if survey_type == 'nps':
            result = HRAgentFacade.analyze_survey(survey_id)
            if "error" in result:
                await update.message.reply_text(f"❌ {result['error']}")
                return
            
            from app.utils.charts import create_nps_chart
            chart_path = create_nps_chart(
                promoters=result.get('promoters', 0),
                passives=result.get('passives', 0),
                detractors=result.get('detractors', 0),
                survey_title=result.get('survey_title', f"Опрос #{survey_id}")
            )
            
            if chart_path and Path(chart_path).exists():
                with open(chart_path, 'rb') as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption=f"📊 **Распределение ответов для опроса #{survey_id}**\n\n"
                               f"🟢 Лояльные: {result.get('promoters', 0)}\n"
                               f"🟡 Равнодушные: {result.get('passives', 0)}\n"
                               f"🔴 Недовольные: {result.get('detractors', 0)}\n\n"
                               f"📈 **NPS Score: {result.get('nps_score', 0)}**"
                    )
                Path(chart_path).unlink()
            else:
                await update.message.reply_text("❌ Не удалось создать график")
        
        elif survey_type == 'pulse':
            from app.db.survey_db import get_responses
            responses = get_responses(survey_id)
            if not responses:
                await update.message.reply_text("❌ Нет ответов для построения графика")
                return
            
            responses_sorted = sorted(responses, key=lambda x: x.get('created_at', ''))
            
            satisfaction_scores = []
            energy_scores = []
            dates = []
            
            for r in responses_sorted:
                answers = r.get('answers', {})
                created = r.get('created_at', '')
                if created:
                    if isinstance(created, str):
                        dates.append(created[:10])
                    else:
                        dates.append(created.strftime('%Y-%m-%d'))

                sat_value = None
                for key in ['satisfaction', 'satisfaction_score', 'sat', 'satisfaction_1']:
                    if key in answers and answers[key] is not None:
                        sat_value = answers[key]
                        break

                eng_value = None
                for key in ['energy', 'energy_score', 'eng', 'energy_1']:
                    if key in answers and answers[key] is not None:
                        eng_value = answers[key]
                        break

                if sat_value is None and eng_value is None:
                    numeric_values = [v for v in answers.values() if isinstance(v, (int, float)) and v is not None]
                    if len(numeric_values) >= 2:
                        sat_value = numeric_values[0]
                        eng_value = numeric_values[1]
                    elif len(numeric_values) == 1:
                        sat_value = numeric_values[0]
                
                if sat_value is not None:
                    satisfaction_scores.append(float(sat_value))
                if eng_value is not None:
                    energy_scores.append(float(eng_value))
            
            if not satisfaction_scores:
                sample_answers = responses_sorted[0].get('answers', {}) if responses_sorted else {}
                await update.message.reply_text(
                    f"❌ Нет данных для построения графика\n\n"
                    f"Структура ответов: {sample_answers}\n\n"
                    f"Пожалуйста, пройдите опрос заново, чтобы данные сохранились корректно."
                )
                return
            
            from app.utils.charts import create_pulse_chart
            chart_path = create_pulse_chart(
                satisfaction_scores=satisfaction_scores,
                energy_scores=energy_scores[:len(satisfaction_scores)],
                dates=dates[:len(satisfaction_scores)],
                survey_title=survey.get('title', f"Опрос #{survey_id}")
            )
            
            if chart_path and Path(chart_path).exists():
                with open(chart_path, 'rb') as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption=f"📈 **Динамика Pulse опроса #{survey_id}**\n\n"
                               f"📊 Удовлетворённость (средняя): {sum(satisfaction_scores)/len(satisfaction_scores):.1f}/5\n"
                               f"⚡ Энергия (средняя): {sum(energy_scores)/len(energy_scores):.1f}/5\n"
                               f"📋 Всего ответов: {len(responses)}"
                    )
                os.unlink(chart_path)
            else:
                await update.message.reply_text("❌ Не удалось создать график")
        
        else:
            await update.message.reply_text(f"❌ Неизвестный тип опроса: {survey_type}")
    else:
        await update.message.reply_text("❌ Укажите ID опроса. Пример: 'график опроса 5'")


async def nps_chart_command(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        survey_id = int(numbers[0])
        await update.message.reply_text("📊 Строю график NPS... Подождите секунду.")
        
        result = HRAgentFacade.analyze_survey(survey_id)
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
            return
        
        if result.get('survey_type') != 'nps':
            await update.message.reply_text("❌ Этот опрос не является NPS опросом")
            return
        
        from app.utils.charts import create_nps_chart
        chart_path = create_nps_chart(
            promoters=result.get('promoters', 0),
            passives=result.get('passives', 0),
            detractors=result.get('detractors', 0),
            survey_title=result.get('survey_title', f"Опрос #{survey_id}")
        )
        
        if chart_path and Path(chart_path).exists():
            with open(chart_path, 'rb') as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"📊 **Распределение ответов для опроса #{survey_id}**\n\n"
                           f"🟢 Лояльные: {result.get('promoters', 0)}\n"
                           f"🟡 Равнодушные: {result.get('passives', 0)}\n"
                           f"🔴 Недовольные: {result.get('detractors', 0)}\n\n"
                           f"📈 **NPS Score: {result.get('nps_score', 0)}**"
                )
            Path(chart_path).unlink()
        else:
            await update.message.reply_text("❌ Не удалось создать график")
    else:
        await update.message.reply_text("❌ Укажите ID опроса. Пример: 'график опроса 1'")


async def pulse_chart_command(update, text):
    numbers = re.findall(r'\d+', text)
    if numbers:
        survey_id = int(numbers[0])
        await update.message.reply_text("📈 Строю график динамики Pulse... Подождите секунду.")
        
        survey = HRAgentFacade.get_survey(survey_id)
        if not survey:
            await update.message.reply_text(f"❌ Опрос с ID {survey_id} не найден")
            return
        
        if survey.get('type') != 'pulse':
            await update.message.reply_text("❌ Этот опрос не является Pulse опросом. Используйте 'график опроса' для NPS.")
            return
        
        from app.db.survey_db import get_responses
        responses = get_responses(survey_id)
        if not responses:
            await update.message.reply_text("❌ Нет ответов для построения графика")
            return
        
        responses_sorted = sorted(responses, key=lambda x: x.get('created_at', ''))
        
        satisfaction_scores = []
        energy_scores = []
        dates = []
        
        for r in responses_sorted:
            answers = r.get('answers', {})

            sat_value = None
            for key in ['satisfaction', 'satisfaction_score', 'sat', 'satisfaction_1']:
                if key in answers and answers[key] is not None:
                    sat_value = answers[key]
                    break

            eng_value = None
            for key in ['energy', 'energy_score', 'eng', 'energy_1']:
                if key in answers and answers[key] is not None:
                    eng_value = answers[key]
                    break

            if sat_value is None and eng_value is None:
                numeric_values = [v for v in answers.values() if isinstance(v, (int, float)) and v is not None]
                if len(numeric_values) >= 2:
                    sat_value = numeric_values[0]
                    eng_value = numeric_values[1]
                elif len(numeric_values) == 1:
                    sat_value = numeric_values[0]
            
            if sat_value is not None:
                satisfaction_scores.append(float(sat_value))
            if eng_value is not None:
                energy_scores.append(float(eng_value))
            
            created = r.get('created_at', '')
            if created:
                if isinstance(created, str):
                    dates.append(created[:10])
                else:
                    dates.append(created.strftime('%Y-%m-%d'))
        
        if not satisfaction_scores:
            await update.message.reply_text(
                f"❌ Нет данных для построения графика\n\n"
                f"Структура ответов: {responses_sorted[0].get('answers', {}) if responses_sorted else 'нет ответов'}"
            )
            return
        
        from app.utils.charts import create_pulse_chart
        chart_path = create_pulse_chart(
            satisfaction_scores=satisfaction_scores,
            energy_scores=energy_scores[:len(satisfaction_scores)],
            dates=dates[:len(satisfaction_scores)],
            survey_title=survey.get('title', f"Опрос #{survey_id}")
        )
        
        if chart_path and Path(chart_path).exists():
            with open(chart_path, 'rb') as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"📈 **Динамика Pulse опроса #{survey_id}**\n\n"
                           f"📊 Удовлетворённость (средняя): {sum(satisfaction_scores)/len(satisfaction_scores):.1f}/5\n"
                           f"⚡ Энергия (средняя): {sum(energy_scores)/len(energy_scores):.1f}/5\n"
                           f"📋 Всего ответов: {len(responses)}"
                )
            os.unlink(chart_path)
        else:
            await update.message.reply_text("❌ Не удалось создать график")
    else:
        await update.message.reply_text("❌ Укажите ID опроса. Пример: 'pulse график 5'")


async def confirm_delete_all_surveys(update, text, user_id, context=None):
    if text.lower() == "да":
        HRAgentFacade.delete_all_surveys()
        
        await update.message.reply_text(
            "✅ **ВСЕ ОПРОСЫ УДАЛЕНЫ!**\n\n"
            "База опросов очищена."
        )
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    elif text.lower() in ["отмена", "нет"]:
        await update.message.reply_text("❌ Удаление отменено.")
        _set_user_state(context, user_id, {})
        _set_temp_data(context, user_id, {})
    else:
        await update.message.reply_text(
            "❌ Непонятный ответ. Напишите **ДА** для подтверждения или **отмена** для отмены."
        )
    return True
