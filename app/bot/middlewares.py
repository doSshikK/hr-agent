"""Middleware для Telegram бота"""

from typing import Callable, Dict, Any, Awaitable
from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class RoleMiddleware:
    """
    Middleware для определения роли пользователя (HR или кандидат).
    Добавляет в данные контекста поле 'role' и 'is_hr'.
    """
    
    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
    ) -> None:
        """
        Обрабатывает каждый апдейт, добавляет роль в context.user_data
        """
        user_id = None
        
        if update.effective_user:
            user_id = update.effective_user.id
        elif update.callback_query and update.callback_query.from_user:
            user_id = update.callback_query.from_user.id
        elif update.message and update.message.from_user:
            user_id = update.message.from_user.id
        
        if user_id:
            is_hr_user = settings.is_hr(user_id)
            
            context.user_data["role"] = "hr" if is_hr_user else "candidate"
            context.user_data["is_hr"] = is_hr_user
            context.user_data["user_id"] = user_id
            
            if hasattr(context, 'bot_data') and "hr_agent" in context.bot_data:
                context.user_data["hr_agent"] = context.bot_data["hr_agent"]
            
            if is_hr_user:
                logger.info(f"🔥 [Middleware] Пользователь {user_id} определён как HR")
            else:
                logger.info(f"✅ [Middleware] Пользователь {user_id} определён как {context.user_data['role']}")
        else:
            logger.warning(f"⚠️ [Middleware] Не удалось определить user_id")
        
        await next_handler(update, context)


class LoggingMiddleware:
    """
    Middleware для логирования всех входящих сообщений и callback'ов
    """
    
    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
    ) -> None:
        """
        Логирует входящие апдейты
        """
        user_id = None
        message_text = None
        callback_data = None
        
        if update.effective_user:
            user_id = update.effective_user.id
        
        if update.message and update.message.text:
            message_text = update.message.text[:200]
            logger.info(f"📨 [Message] Пользователь {user_id}: {message_text}")
        elif update.callback_query:
            callback_data = update.callback_query.data[:200]
            logger.info(f"🔘 [Callback] Пользователь {user_id}: {callback_data}")
        
        await next_handler(update, context)


class ErrorHandlingMiddleware:
    """
    Middleware для глобальной обработки ошибок в хендлерах
    """
    
    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
    ) -> None:
        """
        Перехватывает ошибки и отправляет сообщение пользователю
        """
        try:
            await next_handler(update, context)
        except Exception as e:
            logger.error(f"❌ Ошибка в хендлере: {e}", exc_info=True)
            
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "😕 Произошла ошибка. Попробуйте позже или обратитесь к администратору."
                    )
                except Exception:
                    pass


def get_role(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Возвращает роль пользователя"""
    return context.user_data.get("role", "candidate")


def is_hr(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, является ли пользователь HR"""
    return context.user_data.get("is_hr", False)


def get_user_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращает ID пользователя"""
    return context.user_data.get("user_id", 0)
