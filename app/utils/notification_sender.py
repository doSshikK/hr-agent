"""
app/utils/notification_sender.py
Фоновая отправка агрегированных уведомлений HR
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from app.core.logger import get_logger
from app.core.config import settings
from app.db.candidate_db import (
    get_pending_notifications,
    mark_notification_sent,
    get_pending_notifications_count
)

logger = get_logger(__name__)

BATCH_SIZE = 10          # Сколько уведомлений накапливать для отправки
BATCH_TIMEOUT = 3600     # Или отправлять раз в час (секунды) = 3600
CHECK_INTERVAL = 60      # Проверять очередь каждые 60 секунд


async def send_batch_notification_to_hr(notifications: List[Dict[str, Any]]):
    """Отправляет одно агрегированное сообщение HR"""
    if not notifications:
        return
    
    from app.bot.telegram_bot import send_notification_to_hr
    
    lines = ["📊 **НОВЫЕ КАНДИДАТЫ**"]
    lines.append("")
    lines.append(f"📅 За период: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append("")
    
    for i, n in enumerate(notifications[:10], 1):
        name = n.get('candidate_name', 'Без имени')
        position = n.get('position', 'должность не указана')
        lines.append(f"{i}. **{name}** — {position}")
    
    if len(notifications) > 10:
        lines.append(f"\n... и ещё {len(notifications) - 10} кандидатов")
    
    lines.append("")
    lines.append(f"📋 **Всего новых:** {len(notifications)}")
    lines.append("🔍 Посмотреть всех: `/candidates`")
    lines.append("🔍 Новых за сегодня: `/new_candidates`")
    
    try:
        await send_notification_to_hr("\n".join(lines))
        logger.info(f"📨 Отправлено агрегированное уведомление ({len(notifications)} кандидатов)")
        
        for n in notifications:
            mark_notification_sent(n['id'])
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления: {e}")


async def notification_worker():
    """Фоновый воркер, который каждые N секунд проверяет очередь"""
    logger.info(f"📨 Notification worker запущен (batch_size={BATCH_SIZE}, timeout={BATCH_TIMEOUT}с)")
    
    while True:
        try:
            pending = get_pending_notifications(limit=BATCH_SIZE)
            
            if len(pending) >= BATCH_SIZE:
                logger.info(f"📨 Накопилось {len(pending)} уведомлений, отправляем...")
                await send_batch_notification_to_hr(pending)
            
            elif len(pending) > 0:
                oldest_time = pending[0]['created_at']
                if isinstance(oldest_time, str):
                    oldest_time = datetime.fromisoformat(oldest_time)
                
                time_diff = (datetime.now() - oldest_time).total_seconds()
                if time_diff >= BATCH_TIMEOUT:
                    logger.info(f"📨 Прошёл час, отправляем {len(pending)} уведомлений...")
                    await send_batch_notification_to_hr(pending)
                else:
                    remaining = int(BATCH_TIMEOUT - time_diff)
                    logger.debug(f"⏳ В очереди {len(pending)} уведомлений, отправка через {remaining}с или при {BATCH_SIZE}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в notification_worker: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)


async def notification_worker_sync():
    """Синхронная обёртка для запуска в отдельном потоке (если нужно)"""
    import asyncio
    await notification_worker()


def start_notification_worker():
    """Запускает воркер уведомлений в фоновом потоке с asyncio"""
    try:
        import threading
        import asyncio
        
        def run_async_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(notification_worker())
        
        thread = threading.Thread(target=run_async_worker, daemon=True)
        thread.start()
        logger.info("📨 Notification worker запущен в фоновом потоке")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка запуска notification worker: {e}")
        return False


async def send_immediate_notification(candidate_id: int, name: str, position: str = ""):
    """Отправляет немедленное уведомление о конкретном кандидате"""
    from app.bot.telegram_bot import send_notification_to_hr
    
    message = f"🔔 **СРОЧНО! Новый кандидат**\n\n"
    message += f"👤 **{name}**\n"
    if position:
        message += f"🎯 Должность: {position}\n"
    message += f"🆔 ID: {candidate_id}\n\n"
    message += f"🔍 Посмотреть: `/candidate_{candidate_id}`"
    
    await send_notification_to_hr(message)


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ NOTIFICATION SENDER")
    print("=" * 60)
    
    if not settings.hr_telegram_id:
        print("❌ HR_TELEGRAM_ID не задан в .env")
    else:
        print(f"📨 HR Telegram ID: {settings.hr_telegram_id}")
        print(f"📦 Batch size: {BATCH_SIZE}")
        print(f"⏱️ Timeout: {BATCH_TIMEOUT} секунд")
        
        count = get_pending_notifications_count()
        print(f"\n📊 Ожидающих уведомлений: {count}")
        
        if count > 0:
            pending = get_pending_notifications(limit=BATCH_SIZE)
            print(f"\n📋 Первые {min(len(pending), 5)} уведомлений:")
            for p in pending[:5]:
                print(f"   • ID {p['candidate_id']}: {p['candidate_name']} — {p['position']}")
        
        print("\n✅ Для запуска воркера вызовите start_notification_worker()")
