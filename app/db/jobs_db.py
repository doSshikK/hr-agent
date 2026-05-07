"""
app/db/jobs_db.py
Модуль для работы с вакансиями в базе данных (PostgreSQL)
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.db.postgres_connector import get_connection

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def init_db():
    """Создание базы данных, таблицы, индексов и триггера (PostgreSQL)"""
    with get_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                level TEXT NOT NULL CHECK(level IN ('junior', 'middle', 'senior')),
                skills JSONB,
                experience INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active', 'archived')),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_level ON jobs(level)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")
        
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_jobs_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql'
        """)
        
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_jobs_updated_at') THEN
                    CREATE TRIGGER update_jobs_updated_at
                    BEFORE UPDATE ON jobs
                    FOR EACH ROW
                    EXECUTE FUNCTION update_jobs_updated_at_column();
                END IF;
            END
            $$;
        """)
        
        conn.commit()
        logger.info(f"✅ База вакансий инициализирована (PostgreSQL)")


def _row_to_dict(colnames, row) -> Dict[str, Any]:
    """Преобразует строку БД в словарь с правильной обработкой JSON"""
    if row is None:
        return None
    
    job = dict(zip(colnames, row))
    
    skills = job.get("skills")
    if skills is None:
        job["skills"] = []
    elif isinstance(skills, str):
        try:
            job["skills"] = json.loads(skills)
        except json.JSONDecodeError:
            job["skills"] = []
    elif isinstance(skills, (list, dict)):
        job["skills"] = skills if isinstance(skills, list) else []
    
    return job


def _validate_level(level: str) -> None:
    """Проверяет корректность уровня"""
    valid_levels = {"junior", "middle", "senior"}
    if level not in valid_levels:
        raise ValueError(f"Неверный уровень: {level}. Допустимые: junior, middle, senior")


def _validate_status(status: str) -> None:
    """Проверяет корректность статуса"""
    valid_statuses = {"active", "archived"}
    if status not in valid_statuses:
        raise ValueError(f"Неверный статус: {status}. Допустимые: active, archived")


def _validate_skills(skills) -> None:
    """Проверяет корректность навыков"""
    if skills is not None and not isinstance(skills, list):
        raise ValueError("skills должен быть списком")


def create_job(
    title: str,
    level: str = "middle",
    skills: Optional[List[str]] = None,
    experience: int = 0,
    description: str = ""
) -> int:
    _validate_level(level)
    _validate_skills(skills)
    
    skills_json = json.dumps(skills or [], ensure_ascii=False)
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO jobs (title, level, skills, experience, description)
            VALUES (%s, %s, %s::jsonb, %s, %s)
            RETURNING id
        """, (title, level, skills_json, experience, description))
        
        job_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"✅ Создана вакансия: {title} (ID: {job_id})")
        return job_id

def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    """Получение вакансии по ID"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        colnames = [desc[0] for desc in cur.description]
        return _row_to_dict(colnames, row)


def get_all_jobs(active_only: bool = True) -> List[Dict[str, Any]]:
    """Получение списка всех вакансий"""
    with get_connection() as conn:
        cur = conn.cursor()
        
        if active_only:
            cur.execute("""
                SELECT * FROM jobs 
                WHERE status = 'active' 
                ORDER BY created_at DESC
            """)
        else:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        return [_row_to_dict(colnames, row) for row in rows]


def get_all_jobs_with_status(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получение списка вакансий по статусу"""
    with get_connection() as conn:
        cur = conn.cursor()
        
        if status:
            _validate_status(status)
            cur.execute("""
                SELECT * FROM jobs 
                WHERE status = %s 
                ORDER BY created_at DESC
            """, (status,))
        else:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        return [_row_to_dict(colnames, row) for row in rows]


def update_job(job_id: int, **fields) -> bool:
    """Обновление вакансии"""
    if not fields:
        return False
    
    allowed_fields = {"title", "level", "skills", "experience", "description", "status"}
    for key in fields:
        if key not in allowed_fields:
            raise ValueError(f"Неверное поле: {key}")
    
    if "level" in fields:
        _validate_level(fields["level"])
    
    if "status" in fields:
        _validate_status(fields["status"])
    
    if "skills" in fields:
        _validate_skills(fields["skills"])
        fields["skills"] = json.dumps(fields["skills"], ensure_ascii=False)
    
    set_parts = []
    values = []
    
    for key, value in fields.items():
        if key == "skills":
            set_parts.append(f"{key} = %s::jsonb")
        else:
            set_parts.append(f"{key} = %s")
        values.append(value)
    
    values.append(job_id)
    set_clause = ", ".join(set_parts)
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE jobs
            SET {set_clause}
            WHERE id = %s
        """, values)
        
        conn.commit()
        
        if cur.rowcount > 0:
            logger.info(f"✅ Обновлена вакансия ID: {job_id}")
            return True
        else:
            logger.warning(f"⚠️ Вакансия ID {job_id} не найдена для обновления")
            return False


def archive_job(job_id: int) -> bool:
    """Архивирует вакансию"""
    return update_job(job_id, status="archived")


def activate_job(job_id: int) -> bool:
    """Активирует архивированную вакансию"""
    return update_job(job_id, status="active")


def delete_job(job_id: int) -> bool:
    """Удаляет вакансию"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        conn.commit()
        
        if cur.rowcount > 0:
            logger.info(f"🗑️ Удалена вакансия ID: {job_id}")
            return True
        else:
            logger.warning(f"⚠️ Вакансия ID {job_id} не найдена для удаления")
            return False


def search_jobs(
    skills: Optional[List[str]] = None,
    level: Optional[str] = None,
    min_experience: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Поиск вакансий по навыкам, уровню и опыту"""
    if level:
        _validate_level(level)
    
    _validate_skills(skills)
    
    query = "SELECT * FROM jobs WHERE status = 'active'"
    params = []
    
    if level:
        query += " AND level = %s"
        params.append(level)
    
    if min_experience is not None:
        query += " AND experience >= %s"
        params.append(min_experience)
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        results = []
        for row in rows:
            job = _row_to_dict(colnames, row)
            
            if skills:
                job_skills_lower = [s.lower() for s in job["skills"]]
                skills_lower = [s.lower() for s in skills]
                matched = list(set(skills_lower) & set(job_skills_lower))
                
                if not matched:
                    continue
                
                job["matched_skills"] = matched
            
            results.append(job)
        
        logger.info(f"🔍 Найдено вакансий: {len(results)}")
        return results


def get_jobs_statistics() -> Dict[str, Any]:
    """Возвращает статистику по вакансиям"""
    with get_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM jobs")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'active'")
        active = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'archived'")
        archived = cur.fetchone()[0]
        
        by_level = {}
        for level in ["junior", "middle", "senior"]:
            cur.execute("""
                SELECT COUNT(*) FROM jobs 
                WHERE level = %s AND status = 'active'
            """, (level,))
            count = cur.fetchone()[0]
            
            if count > 0:
                by_level[level] = count
        
        return {
            "total": total,
            "active": active,
            "archived": archived,
            "by_level": by_level
        }


def get_jobs_by_level(level: str) -> List[Dict[str, Any]]:
    """Возвращает все вакансии указанного уровня"""
    _validate_level(level)
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM jobs 
            WHERE level = %s AND status = 'active'
            ORDER BY created_at DESC
        """, (level,))
        
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        return [_row_to_dict(colnames, row) for row in rows]


def get_active_jobs_count() -> int:
    """Возвращает количество активных вакансий"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'active'")
        result = cur.fetchone()
        return result[0] if result else 0


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДУЛЯ JOBS_DB (PostgreSQL)")
    print("=" * 60)
    
    init_db()
    
    print("\n📝 Создание вакансии...")
    job_id = create_job(
        title="Python Developer",
        level="middle",
        skills=["Python", "Django", "PostgreSQL"],
        experience=3,
        description="Разработка backend сервисов"
    )
    print(f"   ✅ Создана с ID: {job_id}")
    
    print("\n🔍 Получение вакансии по ID...")
    job = get_job(job_id)
    print(f"   Название: {job['title']}")
    print(f"   Уровень: {job['level']}")
    print(f"   Навыки: {', '.join(job['skills'])}")
    
    print("\n✏️ Обновление вакансии...")
    update_job(job_id, title="Senior Python Developer", level="senior")
    
    updated_job = get_job(job_id)
    print(f"   Новое название: {updated_job['title']}")
    print(f"   Новый уровень: {updated_job['level']}")
    
    print("\n📋 Все вакансии:")
    all_jobs = get_all_jobs(active_only=False)
    for j in all_jobs:
        print(f"   #{j['id']}: {j['title']} ({j['level']}) - {j['status']}")
    
    print("\n📊 Статистика:")
    stats = get_jobs_statistics()
    print(f"   Всего: {stats['total']}")
    print(f"   Активных: {stats['active']}")
    print(f"   Архивных: {stats['archived']}")
    print(f"   По уровням: {stats['by_level']}")
    
    print("\n🔎 Поиск вакансий...")
    found = search_jobs(skills=["Python"], level="senior")
    print(f"   Найдено: {len(found)}")
    
    print("\n🗑️ Удаление вакансии...")
    delete_job(job_id)
    
    deleted = get_job(job_id)
    print(f"   Вакансия после удаления: {'не найдена' if not deleted else 'найдена!'}")
    
    print("\n✅ Все тесты пройдены!")
