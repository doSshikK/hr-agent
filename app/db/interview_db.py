"""
app/db/interview_db.py
Модуль для работы со слотами собеседований (PostgreSQL)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings
from app.db.postgres_connector import get_connection

logger = logging.getLogger(__name__)


def init_interview_db() -> None:
    """Создаёт таблицы для управления собеседованиями"""
    with get_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS interview_slots (
                id SERIAL PRIMARY KEY,
                hr_id INTEGER NOT NULL,
                slot_date DATE NOT NULL,
                slot_time TIME NOT NULL,
                is_booked BOOLEAN DEFAULT FALSE,
                candidate_id INTEGER,
                booked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(slot_date, slot_time)
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interview_slots_date ON interview_slots(slot_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interview_slots_is_booked ON interview_slots(is_booked)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interview_slots_hr ON interview_slots(hr_id)")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS interview_settings (
                id SERIAL PRIMARY KEY,
                address TEXT DEFAULT 'г. Челябинск, ул. Ленина, 5, офис 301',
                reminder_text TEXT DEFAULT 'Не забудьте паспорт и резюме!',
                working_hours_start TIME DEFAULT '09:00',
                working_hours_end TIME DEFAULT '18:00',
                slot_interval_minutes INTEGER DEFAULT 60,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cur.execute("SELECT COUNT(*) FROM interview_settings")
        count = cur.fetchone()[0]
        if count == 0:
            cur.execute("""
                INSERT INTO interview_settings (address, reminder_text, working_hours_start, working_hours_end, slot_interval_minutes)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                "г. Челябинск, ул. Ленина, 5, офис 301",
                "Не забудьте паспорт и резюме!",
                "09:00",
                "18:00",
                60
            ))
            logger.info("✅ Добавлены настройки собеседований по умолчанию")
        
        conn.commit()
        logger.info("✅ База данных собеседований инициализирована")


def add_slot(hr_id: int, slot_date: str, slot_time: str) -> Tuple[bool, str, Optional[int]]:
    """Добавляет слот для собеседования"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id FROM interview_slots 
                WHERE slot_date = %s AND slot_time = %s
            """, (slot_date, slot_time))
            existing = cur.fetchone()
            
            if existing:
                return False, f"Слот на {slot_date} в {slot_time} уже существует", None
            
            cur.execute("""
                INSERT INTO interview_slots (hr_id, slot_date, slot_time)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (hr_id, slot_date, slot_time))
            
            slot_id = cur.fetchone()[0]
            conn.commit()
            
            logger.info(f"✅ Добавлен слот {slot_id}: {slot_date} {slot_time}")
            return True, f"✅ Слот добавлен: {slot_date} в {slot_time}", slot_id
            
    except Exception as e:
        logger.error(f"❌ Ошибка добавления слота: {e}")
        return False, f"❌ Ошибка: {str(e)}", None


def get_slots_by_hr(hr_id: int) -> List[Dict[str, Any]]:
    """Возвращает все слоты, созданные HR"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, slot_date, slot_time, is_booked, candidate_id, booked_at
            FROM interview_slots 
            WHERE hr_id = %s
            ORDER BY slot_date, slot_time
        """, (hr_id,))
        
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        result = []
        for row in rows:
            slot = dict(zip(colnames, row))
            slot['slot_date'] = str(slot['slot_date']) if slot.get('slot_date') else None
            slot['slot_time'] = str(slot['slot_time']) if slot.get('slot_time') else None
            result.append(slot)
        
        return result


def get_all_slots(only_free: bool = True) -> List[Dict[str, Any]]:
    """Возвращает список всех слотов"""
    with get_connection() as conn:
        cur = conn.cursor()
        
        if only_free:
            cur.execute("""
                SELECT id, slot_date, slot_time, is_booked
                FROM interview_slots 
                WHERE is_booked = FALSE AND slot_date >= CURRENT_DATE
                ORDER BY slot_date, slot_time
            """)
        else:
            cur.execute("""
                SELECT id, slot_date, slot_time, is_booked
                FROM interview_slots 
                ORDER BY slot_date, slot_time
            """)
        
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        result = []
        for row in rows:
            slot = dict(zip(colnames, row))
            slot['slot_date'] = str(slot['slot_date']) if slot.get('slot_date') else None
            slot['slot_time'] = str(slot['slot_time']) if slot.get('slot_time') else None
            result.append(slot)
        
        return result


def delete_slot(slot_id: int, hr_id: int) -> Tuple[bool, str]:
    """Удаляет слот (только если он не забронирован)"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT is_booked FROM interview_slots 
                WHERE id = %s AND hr_id = %s
            """, (slot_id, hr_id))
            row = cur.fetchone()
            
            if not row:
                return False, "Слот не найден"
            
            if row[0]:  # is_booked
                return False, "Нельзя удалить забронированный слот"
            
            cur.execute("DELETE FROM interview_slots WHERE id = %s AND hr_id = %s", (slot_id, hr_id))
            conn.commit()
            
            logger.info(f"🗑️ Удалён слот {slot_id}")
            return True, "Слот удалён"
            
    except Exception as e:
        logger.error(f"❌ Ошибка удаления слота: {e}")
        return False, f"Ошибка: {str(e)}"


def cancel_booking(slot_id: int, hr_id: int = None) -> Tuple[bool, str, Optional[int]]:
    """Отменяет бронирование слота (освобождает его)"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            if hr_id:
                cur.execute("""
                    SELECT id, candidate_id, is_booked FROM interview_slots 
                    WHERE id = %s AND hr_id = %s
                """, (slot_id, hr_id))
            else:
                cur.execute("""
                    SELECT id, candidate_id, is_booked FROM interview_slots 
                    WHERE id = %s
                """, (slot_id,))
            
            row = cur.fetchone()
            
            if not row:
                return False, "Слот не найден", None
            
            if not row[2]:  # is_booked
                return False, "Этот слот не занят", None
            
            candidate_id = row[1]
            
            cur.execute("""
                UPDATE interview_slots 
                SET is_booked = FALSE, candidate_id = NULL, booked_at = NULL
                WHERE id = %s
            """, (slot_id,))
            
            conn.commit()
            
            logger.info(f"🗑️ Отменено бронирование слота {slot_id}, кандидат {candidate_id}")
            return True, "Бронирование отменено, слот свободен", candidate_id
            
    except Exception as e:
        logger.error(f"❌ Ошибка отмены бронирования: {e}")
        return False, f"Ошибка: {str(e)}", None

def cancel_booking_by_candidate(slot_id: int, candidate_db_id: int) -> Tuple[bool, str]:
    """
    Отменяет бронирование слота по запросу кандидата
    Проверяет, что слот принадлежит этому кандидату
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, is_booked FROM interview_slots 
                WHERE id = %s AND candidate_id = %s
            """, (slot_id, candidate_db_id))
            row = cur.fetchone()
            
            if not row:
                return False, "Слот не найден или не принадлежит вам"
            
            if not row[1]:  # is_booked
                return False, "Этот слот не занят"
            
            cur.execute("""
                UPDATE interview_slots 
                SET is_booked = FALSE, candidate_id = NULL, booked_at = NULL
                WHERE id = %s
            """, (slot_id,))
            
            conn.commit()
            
            logger.info(f"🗑️ Кандидат {candidate_db_id} отменил бронирование слота {slot_id}")
            return True, "Собеседование отменено, слот свободен"
            
    except Exception as e:
        logger.error(f"❌ Ошибка отмены бронирования кандидатом: {e}")
        return False, f"Ошибка: {str(e)}"


def get_candidate_slot(candidate_db_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает забронированный слот кандидата (по ID из БД)"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, slot_date, slot_time, is_booked, hr_id
            FROM interview_slots 
            WHERE candidate_id = %s AND is_booked = TRUE
        """, (candidate_db_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "slot_date": str(row[1]),
            "slot_time": str(row[2]),
            "is_booked": row[3],
            "hr_id": row[4]
        }


def get_slot_by_id(slot_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает слот по ID"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, slot_date, slot_time, is_booked, candidate_id, hr_id
            FROM interview_slots 
            WHERE id = %s
        """, (slot_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        colnames = [desc[0] for desc in cur.description]
        slot = dict(zip(colnames, row))
        slot['slot_date'] = str(slot['slot_date'])
        slot['slot_time'] = str(slot['slot_time'])
        
        return slot


def generate_slots_for_date(hr_id: int, date: str, start_time: str = "09:00", end_time: str = "18:00", interval_minutes: int = 60) -> Tuple[int, List[str]]:
    """Генерирует слоты на указанную дату"""
    errors = []
    added = 0
    
    try:
        start = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
        
        current = start
        while current < end:
            slot_time = current.strftime("%H:%M")
            success, msg, _ = add_slot(hr_id, date, slot_time)
            
            if success:
                added += 1
            else:
                errors.append(msg)
            
            current += timedelta(minutes=interval_minutes)
        
        logger.info(f"📅 Сгенерировано {added} слотов на {date}")
        return added, errors
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации слотов: {e}")
        return added, [str(e)]


def get_interview_settings() -> Dict[str, Any]:
    """Возвращает настройки собеседований"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM interview_settings ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        
        if not row:
            return {
                "address": "г. Челябинск, ул. Ленина, 5, офис 301",
                "reminder_text": "Не забудьте паспорт и резюме!",
                "working_hours_start": "09:00",
                "working_hours_end": "18:00",
                "slot_interval_minutes": 60
            }
        
        colnames = [desc[0] for desc in cur.description]
        return dict(zip(colnames, row))


def get_slots_by_date(date: str, hr_id: int = None) -> List[Dict[str, Any]]:
    """Возвращает все слоты на конкретную дату (опционально по HR)"""
    with get_connection() as conn:
        cur = conn.cursor()
        if hr_id:
            cur.execute("""
                SELECT id, slot_date, slot_time, is_booked, candidate_id
                FROM interview_slots 
                WHERE slot_date = %s AND hr_id = %s
                ORDER BY slot_time
            """, (date, hr_id))
        else:
            cur.execute("""
                SELECT id, slot_date, slot_time, is_booked, candidate_id
                FROM interview_slots 
                WHERE slot_date = %s
                ORDER BY slot_time
            """, (date,))
        
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        result = []
        for row in rows:
            slot = dict(zip(colnames, row))
            slot['slot_date'] = str(slot['slot_date']) if slot.get('slot_date') else None
            slot['slot_time'] = str(slot['slot_time']) if slot.get('slot_time') else None
            result.append(slot)
        
        return result


def is_date_fully_booked(date: str, hr_id: int) -> bool:
    """Проверяет, все ли слоты на дату заняты"""
    slots = get_slots_by_date(date, hr_id)
    if not slots:
        return False
    
    booked_count = sum(1 for s in slots if s.get('is_booked'))
    return booked_count == len(slots) and len(slots) > 0


def has_free_slots(date: str, hr_id: int) -> bool:
    """Проверяет, есть ли свободные слоты на дату"""
    slots = get_slots_by_date(date, hr_id)
    if not slots:
        return False
    
    free_count = sum(1 for s in slots if not s.get('is_booked'))
    return free_count > 0


def delete_free_slots_by_date(date: str, hr_id: int) -> Tuple[int, int, List[str]]:
    """
    Удаляет ТОЛЬКО свободные слоты на указанную дату.
    Занятые слоты НЕ трогает.
    
    Returns:
        Tuple[deleted_count, booked_count, errors]
    """
    deleted = 0
    booked_count = 0
    errors = []
    
    slots = get_slots_by_date(date, hr_id)
    
    for slot in slots:
        if slot.get('is_booked'):
            booked_count += 1
            continue  # пропускаем занятые слоты
        
        success, msg = delete_slot(slot['id'], hr_id)
        if success:
            deleted += 1
        else:
            errors.append(f"Слот {slot['slot_time']}: {msg}")
    
    logger.info(f"🗑️ Очистка даты {date}: удалено {deleted} свободных слотов, оставлено {booked_count} занятых")
    return deleted, booked_count, errors


def get_free_slots_grouped_by_date(limit_days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
    """Возвращает свободные слоты, сгруппированные по датам"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, slot_date, slot_time
            FROM interview_slots 
            WHERE is_booked = FALSE 
                AND slot_date >= CURRENT_DATE 
                AND slot_date <= CURRENT_DATE + INTERVAL '%s days'
            ORDER BY slot_date, slot_time
        """, (limit_days,))
        
        rows = cur.fetchall()
        
        result = {}
        for row in rows:
            date = str(row[1])
            if date not in result:
                result[date] = []
            result[date].append({"id": row[0], "slot_time": str(row[2])})
        
        return result


def book_slot(slot_id: int, candidate_db_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Бронирует слот для кандидата (candidate_db_id — это ID из таблицы candidates)"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, slot_date, slot_time, is_booked
                FROM interview_slots 
                WHERE id = %s
            """, (slot_id,))
            row = cur.fetchone()
            
            if not row:
                return False, "Слот не найден", None
            
            if row[3]:  # is_booked
                return False, "Этот слот уже занят", None
            
            cur.execute("""
                UPDATE interview_slots 
                SET is_booked = TRUE, candidate_id = %s, booked_at = NOW()
                WHERE id = %s
            """, (candidate_db_id, slot_id))
            
            conn.commit()
            
            slot_data = {
                "id": row[0],
                "date": str(row[1]),
                "time": str(row[2])
            }
            
            logger.info(f"✅ Слот {slot_id} забронирован кандидатом с ID в БД {candidate_db_id}")
            return True, "Слот успешно забронирован", slot_data
            
    except Exception as e:
        logger.error(f"❌ Ошибка бронирования слота: {e}")
        return False, f"Ошибка: {str(e)}", None


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДУЛЯ INTERVIEW_DB")
    print("=" * 60)
    
    init_interview_db()
    
    print("\n✅ Все функции готовы к использованию!")
