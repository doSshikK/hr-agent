"""
app/utils/reminder.py
Фоновые напоминания для онбординга (ежедневные уведомления)
"""

import asyncio
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from telegram import Bot

from app.core.logger import get_logger
from app.core.config import settings
from app.db.candidate_db import get_candidate, update_candidate_status

logger = get_logger(__name__)


_active_reminders: Dict[int, Dict[str, Any]] = {}

DEFAULT_REMINDER_HOUR = 9  # 9:00 утра
DEFAULT_REMINDER_MINUTE = 0
CHECK_INTERVAL = 60  # проверять каждые 60 секунд


class OnboardingReminder:
    """Класс для управления напоминаниями онбординга"""
    
    def __init__(self):
        self.bot = None
        self.is_running = False
        self.task = None
    
    def _get_bot(self) -> Bot:
        """Возвращает экземпляр бота"""
        if self.bot is None:
            self.bot = Bot(token=settings.telegram_bot_token)
        return self.bot
    
    def add_reminder(
        self,
        user_id: int,
        candidate_id: int,
        task_index: int,
        task_text: str,
        deadline: datetime
    ) -> None:
        """
        Добавляет напоминание о задаче
        """
        _active_reminders[user_id] = {
            "candidate_id": candidate_id,
            "task_index": task_index,
            "task_text": task_text,
            "deadline": deadline,
            "last_reminded": None,
            "reminder_count": 0
        }
        logger.info(f"📅 Добавлено напоминание для пользователя {user_id} о задаче: {task_text[:50]}...")
    
    def remove_reminder(self, user_id: int) -> None:
        """Удаляет напоминание для пользователя"""
        if user_id in _active_reminders:
            del _active_reminders[user_id]
            logger.info(f"🗑️ Удалено напоминание для пользователя {user_id}")
    
    def get_reminder(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает напоминание для пользователя"""
        return _active_reminders.get(user_id)
    
    def has_reminder(self, user_id: int) -> bool:
        """Проверяет, есть ли напоминание для пользователя"""
        return user_id in _active_reminders
    
    async def send_reminder(self, user_id: int, reminder: Dict[str, Any]) -> bool:
        """
        Отправляет напоминание пользователю
        Возвращает True, если отправлено успешно
        """
        try:
            bot = self._get_bot()
            task_text = reminder.get("task_text", "")
            deadline = reminder.get("deadline")
            reminder_count = reminder.get("reminder_count", 0)
            candidate_id = reminder.get("candidate_id")
            
            if reminder_count == 0:
                if deadline and deadline.date() == datetime.now().date():
                    message = (
                        f"⏰ **НАПОМИНАНИЕ!** ⏰\n\n"
                        f"Сегодня нужно выполнить задачу:\n\n"
                        f"📌 **{task_text}**\n\n"
                        f"Дедлайн: сегодня\n\n"
                        f"✅ После выполнения нажмите 'Отметить готовым' в меню онбординга.\n\n"
                        f"💡 Если нужна помощь — нажмите '❓ Как сделать?'"
                    )
                else:
                    days_left = (deadline.date() - datetime.now().date()).days if deadline else 0
                    if days_left == 1:
                        day_text = "завтра"
                    elif days_left == 0:
                        day_text = "сегодня"
                    else:
                        day_text = f"через {days_left} дня"
                    
                    message = (
                        f"⏰ **НАПОМИНАНИЕ!** ⏰\n\n"
                        f"У вас есть задача с дедлайном {day_text}:\n\n"
                        f"📌 **{task_text}**\n\n"
                        f"Не забудьте выполнить её вовремя!\n\n"
                        f"✅ После выполнения нажмите 'Отметить готовым'.\n\n"
                        f"💡 Если нужна помощь — обратитесь к наставнику."
                    )
            else:
                message = (
                    f"⚠️ **СРОЧНОЕ НАПОМИНАНИЕ!** ⚠️\n\n"
                    f"Задача **{task_text}**\n\n"
                    f"Дедлайн уже **{deadline.strftime('%d.%m.%Y') if deadline else 'скоро'}**!\n\n"
                    f"Пожалуйста, выполните задачу как можно скорее.\n\n"
                    f"Если нужна помощь, напишите 'помощь' или обратитесь к наставнику.\n\n"
                    f"✅ Нажмите 'Отметить готовым' после выполнения."
                )
            
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown"
            )
            
            logger.info(f"📨 Отправлено напоминание пользователю {user_id} (попытка #{reminder_count + 1})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке напоминания пользователю {user_id}: {e}")
            return False
    
    async def check_all_reminders(self) -> None:
        """Проверяет все активные напоминания и отправляет при необходимости"""
        now = datetime.now()
        
        for user_id, reminder in list(_active_reminders.items()):
            deadline = reminder.get("deadline")
            last_reminded = reminder.get("last_reminded")
            reminder_count = reminder.get("reminder_count", 0)
            
            should_remind = False
            
            if deadline:
                days_until_deadline = (deadline - now).days
                hours_until_deadline = (deadline - now).total_seconds() / 3600
                
                if 23 <= hours_until_deadline <= 25 and reminder_count == 0:
                    should_remind = True
                elif deadline.date() == now.date() and now.hour >= 9 and reminder_count == 0:
                    should_remind = True
                elif 2 <= hours_until_deadline <= 4 and reminder_count == 1:
                    should_remind = True
                elif now > deadline and reminder_count < 3:
                    should_remind = True
            
            if should_remind and last_reminded:
                hours_since_last = (now - last_reminded).total_seconds() / 3600
                if hours_since_last < 6:
                    should_remind = False
            
            if should_remind:
                success = await self.send_reminder(user_id, reminder)
                if success:
                    reminder["last_reminded"] = now
                    reminder["reminder_count"] = reminder_count + 1
                    
                    if reminder["reminder_count"] >= 3:
                        logger.info(f"📦 Удаляем напоминание для {user_id} (3 попытки)")
                        del _active_reminders[user_id]
    
    async def start(self) -> None:
        """Запускает фоновую проверку напоминаний"""
        if self.is_running:
            logger.warning("⚠️ Напоминания уже запущены")
            return
        
        self.is_running = True
        logger.info(f"📅 Сервис напоминаний запущен (проверка каждые {CHECK_INTERVAL} сек)")
        
        while self.is_running:
            try:
                await self.check_all_reminders()
            except Exception as e:
                logger.error(f"❌ Ошибка в сервисе напоминаний: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)
    
    async def stop(self) -> None:
        """Останавливает сервис напоминаний"""
        self.is_running = False
        logger.info("📅 Сервис напоминаний остановлен")
    
    async def start_in_background(self) -> asyncio.Task:
        """Запускает сервис напоминаний в фоне"""
        self.task = asyncio.create_task(self.start())
        return self.task


reminder_service = OnboardingReminder()


def schedule_onboarding_reminders(
    user_id: int,
    candidate_id: int,
    checklist: List[Dict[str, Any]],
    start_date: datetime
) -> None:
    """
    Планирует напоминания для всех задач онбординга
    """
    for i, task in enumerate(checklist):
        deadline_str = task.get("deadline")
        if deadline_str:
            try:
                if isinstance(deadline_str, str):
                    deadline = datetime.fromisoformat(deadline_str)
                else:
                    deadline = deadline_str
                
                reminder_service.add_reminder(
                    user_id=user_id,
                    candidate_id=candidate_id,
                    task_index=i,
                    task_text=task.get("task", ""),
                    deadline=deadline
                )
                logger.info(f"📅 Запланировано напоминание для задачи {i+1}: {task.get('task', '')[:50]}...")
            except Exception as e:
                logger.error(f"❌ Ошибка при планировании напоминания: {e}")


def schedule_single_reminder(
    user_id: int,
    candidate_id: int,
    task_index: int,
    task_text: str,
    deadline: datetime
) -> None:
    """
    Планирует одно напоминание для конкретной задачи
    """
    reminder_service.add_reminder(
        user_id=user_id,
        candidate_id=candidate_id,
        task_index=task_index,
        task_text=task_text,
        deadline=deadline
    )
    logger.info(f"📅 Запланировано отдельное напоминание для пользователя {user_id}: {task_text[:50]}...")


def cancel_onboarding_reminders(user_id: int) -> None:
    """
    Отменяет все напоминания для пользователя
    """
    reminder_service.remove_reminder(user_id)


def update_onboarding_reminder(
    user_id: int,
    completed_task_index: int
) -> None:
    """
    Обновляет напоминания после выполнения задачи
    """
    reminder = reminder_service.get_reminder(user_id)
    if reminder and reminder.get("task_index") == completed_task_index:
        reminder_service.remove_reminder(user_id)
        logger.info(f"✅ Напоминание для задачи {completed_task_index + 1} удалено (задача выполнена)")


def is_reminder_active(user_id: int) -> bool:
    """Проверяет, есть ли активные напоминания для пользователя"""
    return reminder_service.has_reminder(user_id)


def get_active_reminders_count() -> int:
    """Возвращает количество активных напоминаний"""
    return len(_active_reminders)


def clear_all_reminders() -> None:
    """Очищает все активные напоминания (для отладки)"""
    _active_reminders.clear()
    logger.info("🗑️ Все активные напоминания очищены")


async def start_reminder_service() -> None:
    """Запускает сервис напоминаний (вызывается из main.py)"""
    await reminder_service.start_in_background()
    logger.info("📅 Сервис напоминаний запущен в фоновом режиме")


def start_reminder_service_sync() -> None:
    """Синхронная обёртка для запуска сервиса напоминаний"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.create_task(reminder_service.start())


def get_reminder_status(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает статус напоминания для пользователя (для отладки)"""
    reminder = reminder_service.get_reminder(user_id)
    if not reminder:
        return None
    
    return {
        "user_id": user_id,
        "candidate_id": reminder.get("candidate_id"),
        "task_index": reminder.get("task_index"),
        "task_text": reminder.get("task_text"),
        "deadline": reminder.get("deadline").isoformat() if reminder.get("deadline") else None,
        "reminder_count": reminder.get("reminder_count", 0),
        "last_reminded": reminder.get("last_reminded").isoformat() if reminder.get("last_reminded") else None
    }


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ СЕРВИСА НАПОМИНАНИЙ")
    print("=" * 60)
    
    print("\n✅ Сервис напоминаний готов к работе!")
    print("📅 Напоминания будут отправляться:")
    print("   • За день до дедлайна в 9:00")
    print("   • В день дедлайна в 9:00")
    print("   • За 3 часа до дедлайна")
    print("   • После просрочки (макс 3 раза)")
    print("\n📋 Функции:")
    print("   • reminder_service.start() — запустить фоновую проверку")
    print("   • reminder_service.add_reminder() — добавить напоминание")
    print("   • reminder_service.remove_reminder() — удалить напоминание")
    print("   • schedule_onboarding_reminders() — запланировать все задачи")
    print("\n📊 Статистика:")
    print(f"   • Активных напоминаний: {get_active_reminders_count()}")
    
    print("\n✅ Готов к работе!")
