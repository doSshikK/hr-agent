"""Пагинация с кнопками Далее/Назад"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.core.logger import get_logger
from .utils import format_years

logger = get_logger(__name__)

async def handle_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки пагинации"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    parts = data.split("_")
    if len(parts) < 4:
        return
    
    _, pagination_type, direction, current_page = parts
    current_page = int(current_page)
    
    page_data = context.user_data.get(f"pagination_{pagination_type}")

    if not page_data:
        await query.edit_message_text("❌ Данные устарели. Пожалуйста, повторите запрос.")
        return
    
    items = page_data["items"]
    page_size = page_data.get("page_size", 10)
    title = page_data.get("title", "Список")
    
    total_pages = (len(items) + page_size - 1) // page_size
    
    if direction == "next":
        new_page = current_page + 1
    elif direction == "prev":
        new_page = current_page - 1
    else:
        return
    
    if new_page < 1 or new_page > total_pages:
        return
    
    start = (new_page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    
    output = [f"📋 **{title}** (страница {new_page}/{total_pages})\n"]
    
    for item in page_items:
        if pagination_type == "candidates":
            output.append(f"**#{item.get('id')}** — {item.get('name', 'Без имени')}\n   • Опыт: {format_years(item.get('experience_years', 0))}")
        elif pagination_type == "jobs":
            status_icon = "✅" if item.get('status') == 'active' else "📦"
            level_icon = "🟢" if item.get('level') == 'junior' else "🟡" if item.get('level') == 'middle' else "🔴"
            output.append(f"{status_icon} {level_icon} **#{item.get('id')}** — {item.get('title', '—')} ({item.get('level', '—')})")
            if item.get('skills'):
                output.append(f"   • Навыки: {', '.join(item.get('skills', [])[:4])}")
        elif pagination_type == "surveys":
            status_icon = "✅" if item.get('status') == 'active' else "📦"
            output.append(f"{status_icon} **#{item.get('id')}** — {item.get('title', '—')} ({item.get('type', '—')})")
    
    output.append(f"\n💡 Всего: {len(items)}")
    
    keyboard = []
    if new_page > 1:
        keyboard.append(InlineKeyboardButton("◀️ Назад", callback_data=f"page_{pagination_type}_prev_{new_page}"))
    if new_page < total_pages:
        keyboard.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{pagination_type}_next_{new_page}"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    
    await query.edit_message_text("\n".join(output), reply_markup=reply_markup)
    
    if page_data:
        page_data["current_page"] = new_page
        context.user_data[f"pagination_{pagination_type}"] = page_data
