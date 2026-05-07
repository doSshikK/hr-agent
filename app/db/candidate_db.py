"""
app/db/candidate_db.py
Модуль для работы с кандидатами в базе данных (PostgreSQL)

"""

import json
from app.core.logger import get_logger
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz

from app.core.config import settings
from app.db.postgres_connector import get_connection
from datetime import datetime

logger = get_logger(__name__)

DEFAULT_WEIGHTS = {"skills": 0.5, "exp": 0.3, "pos": 0.2}

SKILL_SYNONYMS = {
    "py": "python", "python3": "python", "python 3": "python",
    "js": "javascript", "es6": "javascript", "ts": "typescript",
    "c++": "cpp", "c#": "csharp",
    "drf": "django", "django rest": "django",
    "flask restful": "flask",
    "pg": "postgresql", "postgres": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes", "gke": "kubernetes",
    "ml": "machine learning", "sklearn": "scikit-learn",
    "amazon web services": "aws", "google cloud platform": "gcp",
    "microsoft azure": "azure"
}


def init_db() -> None:
    """
    Создаёт все таблицы, индексы и триггеры БД кандидатов.

    Архитектурное решение:
    - CREATE TABLE IF NOT EXISTS содержит ВСЕ колонки с самого начала
      (правильное решение для новых установок).
    - _run_migrations() применяет ALTER TABLE для существующих БД,
      которые были созданы старой версией кода.
    - Такое разделение устраняет 15+ ALTER TABLE при каждом старте.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id                      SERIAL PRIMARY KEY,
                name                    TEXT,
                email                   TEXT UNIQUE,
                phone                   TEXT,
                experience_years        INTEGER DEFAULT 0,
                last_position           TEXT,
                last_company            TEXT,
                raw_data                TEXT,
                file_name               TEXT,
                file_hash               TEXT UNIQUE,
                telegram_id             BIGINT,
                source                  TEXT DEFAULT 'telegram',
                status                  TEXT DEFAULT 'candidate',
                hired_position          TEXT,
                salary                  INTEGER,
                hired_at                TIMESTAMP,
                interview_stage         TEXT DEFAULT NULL,
                selected_slot_id        INTEGER,
                onboarding_step         INTEGER DEFAULT 0,
                onboarding_data         TEXT,
                onboarding_started_at   TIMESTAMP,
                onboarding_completed_at TIMESTAMP,
                onboarding_checklist    TEXT,
                resume_data             BYTEA,
                resume_content_type     TEXT,
                created_at              TIMESTAMP DEFAULT NOW(),
                updated_at              TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS deleted_candidates (
                id                INTEGER PRIMARY KEY,
                name              TEXT,
                email             TEXT,
                phone             TEXT,
                experience_years  INTEGER DEFAULT 0,
                last_position     TEXT,
                last_company      TEXT,
                raw_data          TEXT,
                file_name         TEXT,
                file_hash         TEXT,
                skills            TEXT,
                deleted_at        TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS archived_candidates (
                id                INTEGER PRIMARY KEY,
                name              TEXT,
                email             TEXT,
                phone             TEXT,
                experience_years  INTEGER,
                last_position     TEXT,
                last_company      TEXT,
                raw_data          TEXT,
                file_name         TEXT,
                file_hash         TEXT,
                skills            TEXT,
                archived_at       TIMESTAMP DEFAULT NOW(),
                archive_reason    TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id    SERIAL PRIMARY KEY,
                name  TEXT UNIQUE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidate_skills (
                candidate_id  INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                skill_id      INTEGER REFERENCES skills(id)     ON DELETE CASCADE,
                UNIQUE(candidate_id, skill_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id              SERIAL PRIMARY KEY,
                candidate_id    INTEGER NOT NULL,
                candidate_name  TEXT,
                position        TEXT,
                created_at      TIMESTAMP DEFAULT NOW(),
                is_sent         BOOLEAN DEFAULT FALSE
            )
        """)

        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_candidate_skills_candidate ON candidate_skills(candidate_id)",
            "CREATE INDEX IF NOT EXISTS idx_candidate_skills_skill     ON candidate_skills(skill_id)",
            "CREATE INDEX IF NOT EXISTS idx_candidates_experience      ON candidates(experience_years)",
            "CREATE INDEX IF NOT EXISTS idx_candidates_email           ON candidates(email)",
            "CREATE INDEX IF NOT EXISTS idx_candidates_file_hash       ON candidates(file_hash)",
            "CREATE INDEX IF NOT EXISTS idx_candidates_status          ON candidates(status)",
            "CREATE INDEX IF NOT EXISTS idx_candidates_telegram        ON candidates(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_notification_queue_sent    ON notification_queue(is_sent)",
            "CREATE INDEX IF NOT EXISTS idx_archived_candidates_date   ON archived_candidates(archived_at)",
            "CREATE INDEX IF NOT EXISTS idx_archived_candidates_reason ON archived_candidates(archive_reason)",
        ]:
            cur.execute(idx_sql)

        cur.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
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
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_candidates_update'
                ) THEN
                    CREATE TRIGGER trg_candidates_update
                    BEFORE UPDATE ON candidates
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                END IF;
            END $$;
        """)

        conn.commit()

    _run_migrations()
    logger.info("✅ БД кандидатов инициализирована (PostgreSQL)")


def _run_migrations() -> None:
    """
    Применяет ALTER TABLE для БД, созданных старой версией кода.
    Безопасно запускать многократно — IF NOT EXISTS / DO NOTHING.
    Для новых установок это no-op (все колонки уже есть в CREATE TABLE).
    """
    _migrations = [
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'candidate'",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS hired_position TEXT",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS salary INTEGER",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS hired_at TIMESTAMP",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS interview_stage TEXT DEFAULT NULL",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS selected_slot_id INTEGER",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS onboarding_step INTEGER DEFAULT 0",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS onboarding_data TEXT",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS telegram_id BIGINT",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS resume_data BYTEA",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS resume_content_type TEXT",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'telegram'",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS onboarding_started_at TIMESTAMP",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMP",
        "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS onboarding_checklist TEXT",
        "CREATE INDEX IF NOT EXISTS idx_candidates_telegram ON candidates(telegram_id)",
    ]
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            for sql in _migrations:
                cur.execute(sql)
            conn.commit()
        logger.debug(f"✅ Migrations applied ({len(_migrations)} statements)")
    except Exception as e:
        logger.warning(f"Migration warning (non-critical): {e}")


def normalize_skill(skill: str) -> str:
    """Нормализует название навыка (приводит к стандартному виду)"""
    if not skill:
        return ""
    normalized = SKILL_SYNONYMS.get(skill.lower().strip(), skill.lower().strip())
    return normalized


def normalize_skills_list(skills: List[str]) -> List[str]:
    """Нормализует список навыков"""
    return [normalize_skill(s) for s in skills if s]


def _add_skill(conn, skill_name: str) -> int:
    """Внутренняя функция добавления навыка с существующим соединением"""
    skill_name = normalize_skill(skill_name)
    cur = conn.cursor()
    cur.execute("INSERT INTO skills(name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (skill_name,))
    cur.execute("SELECT id FROM skills WHERE name = %s", (skill_name,))
    result = cur.fetchone()
    return result[0] if result else 0


def get_candidate_skills(candidate_id: int) -> List[str]:
    """Возвращает список навыков кандидата"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.name 
            FROM skills s 
            JOIN candidate_skills cs ON cs.skill_id = s.id 
            WHERE cs.candidate_id = %s
        """, (candidate_id,))
        rows = cur.fetchall()
        return [row[0] for row in rows]


def calculate_file_hash(file_path: str) -> Optional[str]:
    """Вычисляет MD5 хеш файла для предотвращения дубликатов"""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Ошибка при вычислении хеша файла {file_path}: {e}")
        return None


def save_candidate(candidate: Dict[str, Any], file_path: str = None) -> int:
    logger.info(f"🔍 save_candidate начат: file_path={file_path}")
    
    candidate_id = None
    file_hash = candidate.get("file_hash")
    if not file_hash and file_path:
        file_hash = calculate_file_hash(file_path)
    email = candidate.get("email")
    telegram_id = candidate.get("telegram_id")
    source = candidate.get("source")
    
    with get_connection() as conn:
        cur = conn.cursor()
        
        if file_hash:
            cur.execute("SELECT id, source FROM candidates WHERE file_hash = %s", (file_hash,))
            existing = cur.fetchone()
            if existing:
                candidate_id = existing[0]
                existing_source = existing[1]
                if existing_source == "email" and source == "telegram":
                    source = "email"
                logger.info(f"Кандидат уже существует по file_hash (ID: {candidate_id})")
        
        if not candidate_id and email:
            cur.execute("SELECT id, source FROM candidates WHERE email = %s", (email,))
            existing = cur.fetchone()
            if existing:
                candidate_id = existing[0]
                existing_source = existing[1]
                if existing_source == "email" and source == "telegram":
                    source = "email"
                logger.info(f"Кандидат уже существует по email (ID: {candidate_id})")
        
        if candidate_id:
            cur.execute("""
                UPDATE candidates 
                SET name = %s, 
                    phone = %s, 
                    experience_years = %s, 
                    last_position = %s, 
                    last_company = %s, 
                    raw_data = %s, 
                    file_name = %s, 
                    file_hash = %s,
                    telegram_id = COALESCE(%s, telegram_id),
                    source = COALESCE(%s, source),
                    updated_at = NOW()
                WHERE id = %s
            """, (
                candidate.get("name"),
                candidate.get("phone"),
                candidate.get("experience_years", 0),
                candidate.get("last_position"),
                candidate.get("last_company"),
                json.dumps(candidate, ensure_ascii=False),
                candidate.get("file_name") or (Path(file_path).name if file_path else None),
                file_hash,
                telegram_id,
                source,
                candidate_id
            ))
            logger.info(f"Кандидат обновлён (ID: {candidate_id}, telegram_id={telegram_id}, source={source})")
        
        else:
            cur.execute("""
                INSERT INTO candidates (
                    name, email, phone, experience_years, last_position, 
                    last_company, raw_data, file_name, file_hash, telegram_id, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                candidate.get("name"),
                email,
                candidate.get("phone"),
                candidate.get("experience_years", 0),
                candidate.get("last_position"),
                candidate.get("last_company"),
                json.dumps(candidate, ensure_ascii=False),
                candidate.get("file_name") or (Path(file_path).name if file_path else None),
                file_hash,
                telegram_id,
                source or "telegram"
            ))
            candidate_id = cur.fetchone()[0]
            logger.info(f"Создан новый кандидат (ID: {candidate_id}, telegram_id={telegram_id}, source={source or 'telegram'})")
        
        if candidate_id:
            cur.execute("DELETE FROM candidate_skills WHERE candidate_id = %s", (candidate_id,))
            
            for skill in normalize_skills_list(candidate.get("skills", [])):
                skill_id = _add_skill(conn, skill)
                if skill_id:
                    cur.execute("""
                        INSERT INTO candidate_skills(candidate_id, skill_id) 
                        VALUES (%s, %s) 
                        ON CONFLICT DO NOTHING
                    """, (candidate_id, skill_id))
        
        if file_path and Path(file_path).exists():
            logger.info(f"🔍 Сохраняем резюме для candidate_id={candidate_id}, file_path={file_path}")
            try:
                with open(file_path, 'rb') as f:
                    resume_data = f.read()
                
                ext = Path(file_path).suffix.lower()
                content_type = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                
                cur.execute("""
                    UPDATE candidates 
                    SET resume_data = %s, resume_content_type = %s
                    WHERE id = %s
                """, (resume_data, content_type, candidate_id))
                
                logger.info(f"✅ Резюме кандидата {candidate_id} сохранено в БД ({len(resume_data)} байт)")
                
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения резюме: {e}")
        else:
            logger.warning(f"⚠️ Файл НЕ сохранён: file_path={file_path}, exists={Path(file_path).exists() if file_path else False}")
        
        conn.commit()
    
    return candidate_id


def get_candidate(candidate_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает кандидата по ID"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM candidates WHERE id = %s", (candidate_id,))
        row = cur.fetchone()
        if not row:
            return None
        
        colnames = [desc[0] for desc in cur.description]
        result = dict(zip(colnames, row))
        result["skills"] = get_candidate_skills(candidate_id)
        return result


def get_candidate_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает кандидата по Telegram ID"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM candidates WHERE telegram_id = %s", (telegram_id,))
        row = cur.fetchone()
        if not row:
            return None
        
        colnames = [desc[0] for desc in cur.description]
        result = dict(zip(colnames, row))
        result["skills"] = get_candidate_skills(result["id"])
        return result


def get_all_candidates(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Возвращает список всех кандидатов"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, email, phone, experience_years, last_position, last_company, created_at, status, hired_position, salary, interview_stage, telegram_id, source
            FROM candidates 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """, (limit, offset))
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        result = []
        for row in rows:
            cand = dict(zip(colnames, row))
            cand["skills"] = get_candidate_skills(cand["id"])
            result.append(cand)
        
        return result


def get_all_candidates_full() -> List[Dict[str, Any]]:
    """Возвращает всех кандидатов с полными данными (без ограничений)"""
    return get_all_candidates(limit=10000)


def update_candidate_status(candidate_id: int, status: str = None, **kwargs) -> bool:
    """Обновляет статус кандидата и дополнительные поля"""
    
    ALLOWED_FIELDS = {
        "hired_position", "salary", "hired_at",
        "onboarding_step", "onboarding_data", "onboarding_started_at",
        "onboarding_completed_at", "onboarding_checklist",
        "interview_stage", "selected_slot_id"
    }
    
    with get_connection() as conn:
        cur = conn.cursor()
        
        fields = []
        values = []
        
        if status is not None:
            fields.append("status = %s")
            values.append(status)
        
        for key in list(kwargs.keys()):
            if key not in ALLOWED_FIELDS:
                logger.warning(f"⚠️ Игнорируем запрещённое поле: {key}")
                del kwargs[key]  # Удаляем запрещённое поле
        
        if "hired_position" in kwargs:
            fields.append("hired_position = %s")
            values.append(kwargs["hired_position"])
        
        if "salary" in kwargs:
            fields.append("salary = %s")
            values.append(kwargs["salary"])
        
        if "hired_at" in kwargs:
            fields.append("hired_at = %s")
            values.append(kwargs["hired_at"])
        
        if "onboarding_step" in kwargs:
            fields.append("onboarding_step = %s")
            values.append(kwargs["onboarding_step"])
        
        if "onboarding_data" in kwargs:
            fields.append("onboarding_data = %s")
            values.append(json.dumps(kwargs["onboarding_data"], ensure_ascii=False))
        
        if "onboarding_started_at" in kwargs:
            fields.append("onboarding_started_at = %s")
            values.append(kwargs["onboarding_started_at"])
        
        if "onboarding_completed_at" in kwargs:
            fields.append("onboarding_completed_at = %s")
            values.append(kwargs["onboarding_completed_at"])
        
        if "onboarding_checklist" in kwargs:
            fields.append("onboarding_checklist = %s")
            values.append(json.dumps(kwargs["onboarding_checklist"], ensure_ascii=False))
        
        if "interview_stage" in kwargs:
            fields.append("interview_stage = %s")
            values.append(kwargs["interview_stage"])
        
        if "selected_slot_id" in kwargs:
            fields.append("selected_slot_id = %s")
            values.append(kwargs["selected_slot_id"])
        
        if not fields:
            return False
        
        values.append(candidate_id)
        
        query = f"UPDATE candidates SET {', '.join(fields)} WHERE id = %s"
        cur.execute(query, values)
        conn.commit()
        
        logger.info(f"✅ Статус кандидата {candidate_id} обновлён")
        return cur.rowcount > 0


def delete_candidate(candidate_id: int) -> bool:
    logger.info(f"🔍 delete_candidate начат для ID: {candidate_id}")
    
    cand = get_candidate(candidate_id)
    if not cand:
        logger.warning(f"Кандидат {candidate_id} не найден")
        return False
    
    skills_list = cand.get("skills", [])
    if isinstance(skills_list, dict):
        skills_list = list(skills_list.values()) if skills_list else []
    elif not isinstance(skills_list, list):
        skills_list = []
    
    skills_json = json.dumps(skills_list, ensure_ascii=False)
    
    raw_data = cand.get("raw_data")
    if isinstance(raw_data, dict):
        raw_data = json.dumps(raw_data, ensure_ascii=False)
    elif raw_data is None:
        raw_data = None
    
    last_position = cand.get("last_position")
    if isinstance(last_position, dict):
        last_position = str(last_position)
    
    last_company = cand.get("last_company")
    if isinstance(last_company, dict):
        last_company = str(last_company)
    
    file_name = cand.get("file_name")
    if isinstance(file_name, dict):
        file_name = str(file_name)
    
    file_hash = cand.get("file_hash")
    if isinstance(file_hash, dict):
        file_hash = str(file_hash)
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO deleted_candidates (
                    id, name, email, phone, experience_years, last_position, 
                    last_company, raw_data, file_name, file_hash, skills
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cand.get("id"),
                cand.get("name"),
                cand.get("email"),
                cand.get("phone"),
                cand.get("experience_years", 0),
                last_position,
                last_company,
                raw_data,
                file_name,
                file_hash,
                skills_json  # Это строка JSON
            ))
            
            cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ Ошибка в delete_candidate: {e}")
        raise
    
    logger.info(f"🗑️ Кандидат #{candidate_id} перемещён в корзину")
    return True

def restore_candidate(candidate_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM deleted_candidates WHERE id = %s", (candidate_id,))
        deleted_row = cur.fetchone()
        if not deleted_row:
            return False
        
        colnames = [desc[0] for desc in cur.description]
        deleted = dict(zip(colnames, deleted_row))
        
        raw_data = deleted.get("raw_data")
        if isinstance(raw_data, dict):
            raw_data = json.dumps(raw_data, ensure_ascii=False)
        
        skills_str = deleted.get("skills", "[]")
        if isinstance(skills_str, dict):
            skills_str = json.dumps(list(skills_str.values()), ensure_ascii=False)
        elif not isinstance(skills_str, str):
            skills_str = "[]"
        
        cur.execute("""
            INSERT INTO candidates (
                id, name, email, phone, experience_years, last_position, 
                last_company, raw_data, file_name, file_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            deleted.get("id"),
            deleted.get("name"),
            deleted.get("email"),
            deleted.get("phone"),
            deleted.get("experience_years", 0),
            deleted.get("last_position"),
            deleted.get("last_company"),
            raw_data,
            deleted.get("file_name"),
            deleted.get("file_hash")
        ))
        
        skills = json.loads(skills_str) if skills_str else []
        for skill in skills:
            if skill and skill.strip():
                skill_id = _add_skill(conn, skill)
                if skill_id:
                    cur.execute("""
                        INSERT INTO candidate_skills(candidate_id, skill_id) 
                        VALUES (%s, %s) 
                        ON CONFLICT DO NOTHING
                    """, (candidate_id, skill_id))
        
        cur.execute("DELETE FROM deleted_candidates WHERE id = %s", (candidate_id,))
        conn.commit()
    
    logger.info(f"🔄 Кандидат #{candidate_id} восстановлен из корзины")
    return True


def fuzzy_skill_match(query_skills: List[str], candidate_skills: List[str]) -> List[str]:
    matched = set()
    for q in query_skills:
        for c in candidate_skills:
            if fuzz.ratio(q.lower(), c.lower()) >= settings.fuzzy_match_threshold:
                matched.add(q)
                break
    return list(matched)


def experience_score(candidate_exp: int, required_exp: int) -> float:
    if not required_exp or required_exp <= 0:
        return 1.0
    
    base = min(candidate_exp / required_exp, 1.0)
    bonus = min(max(candidate_exp - required_exp, 0) * 0.05, 0.2)
    return min(base + bonus, 1.2)


def normalize_russian_word(word: str) -> str:
    """Нормализует русское слово (убирает падежные окончания ТОЛЬКО в конце)"""
    if not word:
        return word
    
    word = word.lower()
    
    word = re.sub(r'(а|у|я|е|ы|и|ой|ем)$', '', word)
    
    parts = word.split('-')
    if len(parts) > 1:
        normalized_parts = [re.sub(r'(а|у|я|е|ы|и)$', '', p) for p in parts]
        word = '-'.join(normalized_parts)
    
    return word


def position_score(candidate_position: str, query_position: str) -> float:
    """Сравнивает должности с учётом падежей"""
    if not candidate_position or not query_position:
        return 0.0
    
    cp_lower = candidate_position.lower()
    qp_lower = query_position.lower()
    
    cp_norm = normalize_russian_word(cp_lower)
    qp_norm = normalize_russian_word(qp_lower)
    
    if qp_norm == cp_norm:
        return 1.0
    elif qp_norm in cp_norm:
        return 0.95
    elif qp_lower in cp_lower:
        return 0.9
    elif any(word in cp_lower for word in qp_lower.split()):
        return 0.7
    elif qp_norm in cp_lower:
        return 0.85
    else:
        return 0.0


def text_match_score(candidate: Dict[str, Any], query_text: str) -> float:
    """
    Вычисляет оценку совпадения по тексту (должность, компания, имя)
    Возвращает 1.0 если нашло в должности, 0.9 в компании, 0.8 в имени
    """
    if not query_text:
        return 0.0
    
    query_lower = query_text.lower()
    text_match = 0.0
    
    last_position = candidate.get('last_position')
    if last_position and query_lower in last_position.lower():
        text_match = 1.0
    elif candidate.get('last_company') and query_lower in candidate['last_company'].lower():
        text_match = 0.9
    elif candidate.get('name') and query_lower in candidate['name'].lower():
        text_match = 0.8
    
    return text_match


def calculate_skill_rarity(candidates: List[Dict[str, Any]]) -> Dict[str, float]:
    total = len(candidates) or 1
    counts = {}
    
    for c in candidates:
        for s in c.get("skills", []):
            counts[s.lower()] = counts.get(s.lower(), 0) + 1
    
    return {s: 1 - cnt / total for s, cnt in counts.items()}


def search_candidates(
    query_skills: List[str] = None,
    min_experience: int = None,
    position: str = None,
    query_text: str = None,
    weights: Dict[str, float] = None,
    min_match_percent: int = None
) -> List[Dict[str, Any]]:
    """
    УНИВЕРСАЛЬНЫЙ ПОИСК кандидатов — учитываются ТОЛЬКО указанные критерии!
    - если указана только должность — ищем только по должности (100% при совпадении)
    - если указаны должность и навыки — считаем только их
    - если указаны все три — считаем все три
    - если ничего не указано — возвращаем всех без сортировки
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()
    
    if min_match_percent is None:
        min_match_percent = settings.min_match_percent
    
    if query_skills is None:
        query_skills = []
    
    query_skills = normalize_skills_list(query_skills)
    
    candidates = get_all_candidates(limit=10000)
    if not candidates:
        return []
    
    rarity = calculate_skill_rarity(candidates)
    
    has_skill_criteria = query_skills and len(query_skills) > 0
    has_exp_criteria = min_experience is not None and min_experience > 0
    has_pos_criteria = position is not None and position.strip() != ""
    
    if not has_skill_criteria and not has_exp_criteria and not has_pos_criteria:
        results = []
        for c in candidates:
            results.append({
                **c,
                "match_percent": 0,
                "matched_skills": [],
                "skills_score": 0,
                "exp_score": 0,
                "pos_score": 0,
                "text_score": 0,
                "text_matched_field": None
            })
        logger.info(f"🔍 Поиск без критериев: возвращено {len(results)} кандидатов")
        return results
    
    results = []
    
    for c in candidates:
        
        skills_score = 0
        matched = []
        if has_skill_criteria:
            matched = fuzzy_skill_match(query_skills, c.get("skills", []))
            skills_score = len(matched) / len(query_skills) if query_skills else 0
        
        exp_score = 0
        if has_exp_criteria:
            candidate_exp = c.get("experience_years", 0) or 0
            exp_score = min(candidate_exp / min_experience, 1.0)
        
        pos_score = 0
        if has_pos_criteria:
            candidate_position = c.get("last_position", "") or ""
            pos_score = position_score(candidate_position, position)
        
        
        if has_skill_criteria and skills_score == 0:
            continue
        
        if has_pos_criteria and pos_score == 0:
            continue
        
        if has_exp_criteria and exp_score < 0.5:
            continue
        
        
        total_score = 0
        weight_sum = 0
        
        if has_skill_criteria:
            skill_weight = weights.get("skills", 0.5)
            total_score += skills_score * skill_weight
            weight_sum += skill_weight
        
        if has_exp_criteria:
            exp_weight = weights.get("exp", 0.3)
            total_score += exp_score * exp_weight
            weight_sum += exp_weight
        
        if has_pos_criteria:
            pos_weight = weights.get("pos", 0.2)
            total_score += pos_score * pos_weight
            weight_sum += pos_weight
        
        if weight_sum > 0:
            total_score = total_score / weight_sum
        else:
            total_score = 0
        
        if matched and has_skill_criteria:
            rarity_sum = sum(rarity.get(s.lower(), 0) for s in matched)
            rarity_bonus = min(rarity_sum / len(matched) * 0.05, 0.05)
            total_score = min(total_score + rarity_bonus, 1.0)
        
        match_percent = int(total_score * 100)
        
        
        results.append({
            **c,
            "match_percent": match_percent,
            "matched_skills": matched,
            "skills_score": int(skills_score * 100),
            "exp_score": int(exp_score * 100),
            "pos_score": int(pos_score * 100),
            "text_score": 0,
            "text_matched_field": None
        })
    
    results.sort(key=lambda x: x["match_percent"], reverse=True)
    
    logger.info(f"🔍 Универсальный поиск (критерии: навыки={has_skill_criteria}, опыт={has_exp_criteria}, должность={has_pos_criteria}): найдено {len(results)} кандидатов из {len(candidates)}")
    return results


def match_candidates_to_job(job: Dict[str, Any], top_n: int = 5) -> List[Dict[str, Any]]:
    """Подбирает кандидатов под вакансию"""
    return search_candidates(
        query_skills=job.get("skills", []),
        min_experience=job.get("experience"),
        position=job.get("title"),
        min_match_percent=0
    )[:top_n]


def add_to_notification_queue(candidate_id: int, name: str, position: str = "") -> None:
    """Добавляет кандидата в очередь уведомлений"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notification_queue (candidate_id, candidate_name, position)
            VALUES (%s, %s, %s)
        """, (candidate_id, name, position))
        conn.commit()
        logger.debug(f"📨 Кандидат ID {candidate_id} добавлен в очередь уведомлений")


def is_candidate_already_in_queue(candidate_id: int, hours: int = 24) -> bool:
    """Проверяет, есть ли уже кандидат в очереди уведомлений за последние N часов"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM notification_queue 
            WHERE candidate_id = %s 
            AND is_sent = FALSE
            AND created_at > NOW() - INTERVAL '%s HOUR'
            LIMIT 1
        """, (candidate_id, hours))
        row = cur.fetchone()
        return row is not None


def get_pending_notifications(limit: int = 10) -> List[Dict[str, Any]]:
    """Получает непрочитанные уведомления"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, candidate_id, candidate_name, position, created_at
            FROM notification_queue
            WHERE is_sent = FALSE
            ORDER BY created_at ASC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        return [dict(zip(colnames, row)) for row in rows]


def mark_notification_sent(notification_id: int) -> None:
    """Отмечает уведомление как отправленное"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE notification_queue SET is_sent = TRUE WHERE id = %s", (notification_id,))
        conn.commit()
        logger.debug(f"✅ Уведомление {notification_id} отмечено как отправленное")


def get_pending_notifications_count() -> int:
    """Возвращает количество непрочитанных уведомлений"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM notification_queue WHERE is_sent = FALSE")
        result = cur.fetchone()
        return result[0] if result else 0


def clear_sent_notifications() -> None:
    """Очищает отправленные уведомления (опционально)"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM notification_queue WHERE is_sent = TRUE")
        conn.commit()
        logger.info("🗑️ Отправленные уведомления очищены")


def archive_candidate(candidate_id: int, reason: str = None) -> bool:
    """
    Перемещает кандидата в архив с указанием причины.
    Причины: 'hired' (нанят), 'rejected' (отказ), 'manual' (ручной)
    """
    logger.info(f"🔍 archive_candidate начат для ID: {candidate_id}, причина: {reason}")
    
    cand = get_candidate(candidate_id)
    if not cand:
        logger.warning(f"Кандидат {candidate_id} не найден")
        return False
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM archived_candidates WHERE id = %s", (candidate_id,))
        if cur.fetchone():
            logger.warning(f"Кандидат {candidate_id} уже в архиве")
            return False
    
    skills_list = cand.get("skills", [])
    if isinstance(skills_list, dict):
        skills_list = list(skills_list.values()) if skills_list else []
    elif not isinstance(skills_list, list):
        skills_list = []
    skills_json = json.dumps(skills_list, ensure_ascii=False)
    
    raw_data = cand.get("raw_data")
    if isinstance(raw_data, dict):
        raw_data = json.dumps(raw_data, ensure_ascii=False)
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO archived_candidates (
                    id, name, email, phone, experience_years, last_position, 
                    last_company, raw_data, file_name, file_hash, skills, archive_reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cand.get("id"),
                cand.get("name"),
                cand.get("email"),
                cand.get("phone"),
                cand.get("experience_years", 0),
                cand.get("last_position"),
                cand.get("last_company"),
                raw_data,
                cand.get("file_name"),
                cand.get("file_hash"),
                skills_json,
                reason or "manual"
            ))
            
            cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
            conn.commit()
            
            logger.info(f"📦 Кандидат #{candidate_id} перемещён в архив (причина: {reason or 'manual'})")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка при архивации кандидата {candidate_id}: {e}")
        return False


def restore_from_archive(candidate_id: int) -> bool:
    """Восстанавливает кандидата из архива обратно в основную таблицу"""
    logger.info(f"🔍 restore_from_archive начат для ID: {candidate_id}")
    
    with get_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM archived_candidates WHERE id = %s", (candidate_id,))
        archived_row = cur.fetchone()
        if not archived_row:
            logger.warning(f"Кандидат {candidate_id} не найден в архиве")
            return False
        
        colnames = [desc[0] for desc in cur.description]
        archived = dict(zip(colnames, archived_row))
        
        cur.execute("""
            INSERT INTO candidates (
                id, name, email, phone, experience_years, last_position, 
                last_company, raw_data, file_name, file_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            archived.get("id"),
            archived.get("name"),
            archived.get("email"),
            archived.get("phone"),
            archived.get("experience_years", 0),
            archived.get("last_position"),
            archived.get("last_company"),
            archived.get("raw_data"),
            archived.get("file_name"),
            archived.get("file_hash")
        ))
        
        skills_str = archived.get("skills", "[]")
        if isinstance(skills_str, str):
            try:
                skills = json.loads(skills_str) if skills_str else []
            except:
                skills = []
        else:
            skills = []
        
        for skill in skills:
            if skill and skill.strip():
                skill_id = _add_skill(conn, skill)
                if skill_id:
                    cur.execute("""
                        INSERT INTO candidate_skills(candidate_id, skill_id) 
                        VALUES (%s, %s) 
                        ON CONFLICT DO NOTHING
                    """, (candidate_id, skill_id))
        
        cur.execute("DELETE FROM archived_candidates WHERE id = %s", (candidate_id,))
        conn.commit()
    
    logger.info(f"🔄 Кандидат #{candidate_id} восстановлен из архива")
    return True


def get_archived_candidates(limit: int = 100) -> List[Dict[str, Any]]:
    """Возвращает список кандидатов в архиве"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, email, phone, experience_years, last_position, 
                   last_company, archived_at, archive_reason
            FROM archived_candidates 
            ORDER BY archived_at DESC 
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        result = []
        for row in rows:
            cand = dict(zip(colnames, row))
            result.append(cand)
        
        return result


def is_candidate_archived(candidate_id: int) -> bool:
    """Проверяет, находится ли кандидат в архиве"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM archived_candidates WHERE id = %s", (candidate_id,))
        return cur.fetchone() is not None


def delete_archived_candidate(candidate_id: int) -> bool:
    """Навсегда удаляет одного кандидата из архива."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM archived_candidates WHERE id = %s", (candidate_id,))
        deleted = cur.rowcount > 0
        conn.commit()

    if deleted:
        logger.info(f"🗑️ Кандидат #{candidate_id} навсегда удалён из архива")
    else:
        logger.warning(f"Кандидат {candidate_id} не найден в архиве для удаления")
    return deleted


def delete_all_archived_candidates() -> int:
    """Навсегда удаляет всех кандидатов из архива и возвращает количество удалённых."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM archived_candidates")
        deleted_count = cur.rowcount
        conn.commit()

    logger.info(f"🗑️ Архив кандидатов очищен, удалено записей: {deleted_count}")
    return deleted_count


def save_onboarding_progress(candidate_id: int, step: int, completed_tasks: List[Dict]) -> bool:
    """Сохраняет прогресс онбординга кандидата"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            onboarding_data = {
                "completed_tasks": completed_tasks,
                "last_updated": datetime.now().isoformat()
            }
            
            cur.execute("""
                UPDATE candidates 
                SET onboarding_step = %s, 
                    onboarding_data = %s
                WHERE id = %s
            """, (
                step,
                json.dumps(onboarding_data, ensure_ascii=False),
                candidate_id
            ))
            conn.commit()
            logger.info(f"✅ Сохранён прогресс онбординга для кандидата {candidate_id}, шаг {step}")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения прогресса онбординга: {e}")
        return False


def get_onboarding_progress(candidate_id: int) -> Dict[str, Any]:
    """Возвращает прогресс онбординга кандидата"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT onboarding_step, onboarding_data, onboarding_started_at, onboarding_completed_at
                FROM candidates 
                WHERE id = %s
            """, (candidate_id,))
            row = cur.fetchone()
            
            if not row:
                return {"step": 0, "completed_tasks": [], "started_at": None, "completed_at": None}
            
            step = row[0] or 0
            onboarding_data = row[1]
            started_at = row[2]
            completed_at = row[3]
            
            completed_tasks = []
            if onboarding_data:
                try:
                    data = json.loads(onboarding_data)
                    completed_tasks = data.get("completed_tasks", [])
                except:
                    pass
            
            return {
                "step": step,
                "completed_tasks": completed_tasks,
                "started_at": started_at,
                "completed_at": completed_at
            }
    except Exception as e:
        logger.error(f"❌ Ошибка получения прогресса онбординга: {e}")
        return {"step": 0, "completed_tasks": [], "started_at": None, "completed_at": None}


def start_onboarding(candidate_id: int) -> bool:
    """Отмечает начало онбординга"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE candidates 
                SET onboarding_started_at = NOW(),
                    onboarding_step = 0
                WHERE id = %s AND (onboarding_started_at IS NULL OR onboarding_started_at IS NULL)
            """, (candidate_id,))
            conn.commit()
            logger.info(f"✅ Онбординг начат для кандидата {candidate_id}")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка начала онбординга: {e}")
        return False


def complete_onboarding(candidate_id: int) -> bool:
    """Отмечает завершение онбординга"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE candidates 
                SET onboarding_completed_at = NOW()
                WHERE id = %s
            """, (candidate_id,))
            conn.commit()
            logger.info(f"✅ Онбординг завершён для кандидата {candidate_id}")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка завершения онбординга: {e}")
        return False


def has_resume_in_db(candidate_id: int) -> bool:
    """Проверяет, есть ли резюме кандидата в БД"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 1 FROM candidates 
                WHERE id = %s AND resume_data IS NOT NULL
            """, (candidate_id,))
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"❌ Ошибка проверки резюме: {e}")
        return False


def get_resume_from_db(candidate_id: int) -> Optional[tuple]:
    """
    Возвращает (resume_data, content_type, filename)
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT resume_data, resume_content_type 
                FROM candidates 
                WHERE id = %s AND resume_data IS NOT NULL
            """, (candidate_id,))
            row = cur.fetchone()
            
            if not row or row[0] is None:
                return None
            
            resume_data = row[0]
            content_type = row[1] or "application/pdf"
            
            ext = ".pdf" if "pdf" in content_type else ".docx"
            filename = f"resume_{candidate_id}{ext}"
            
            return (resume_data, content_type, filename)
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения резюме из БД: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДУЛЯ CANDIDATE_DB (PostgreSQL)")
    print("=" * 60)
    
    init_db()
    
    test_candidate = {
        "name": "Тестов Тест Тестович",
        "email": "test@example.com",
        "phone": "+79001234567",
        "skills": ["Python", "Django", "PostgreSQL"],
        "experience_years": 5,
        "last_position": "Senior Python Developer",
        "last_company": "Тестовая Компания"
    }
    
    print("\n📝 Сохранение кандидата...")
    candidate_id = save_candidate(test_candidate, None)
    print(f"   ✅ Сохранён с ID: {candidate_id}")
    
    print("\n🔍 Получение кандидата по ID...")
    saved = get_candidate(candidate_id)
    print(f"   Имя: {saved['name']}")
    print(f"   Навыки: {', '.join(saved['skills'])}")
    
    print("\n🔎 Поиск кандидатов по навыкам...")
    results = search_candidates(query_skills=["Python", "Django"])
    print(f"   Найдено: {len(results)}")
    
    if results:
        print(f"   Лучший кандидат: {results[0]['name']} ({results[0]['match_percent']}%)")
    
    print("\n🗑️ Удаление кандидата...")
    delete_candidate(candidate_id)
    
    deleted = get_candidate(candidate_id)
    print(f"   Кандидат после удаления: {'не найден' if not deleted else 'найден!'}")
    
    print("\n📨 Тест очереди уведомлений...")
    add_to_notification_queue(1, "Тестовый кандидат", "Python Developer")
    pending = get_pending_notifications(limit=5)
    print(f"   Ожидающих уведомлений: {len(pending)}")
    count = get_pending_notifications_count()
    print(f"   Всего в очереди: {count}")
    if pending:
        mark_notification_sent(pending[0]['id'])
        print(f"   Уведомление {pending[0]['id']} отмечено отправленным")
    
    print("\n📨 Тест проверки дубликатов в очереди:")
    is_already = is_candidate_already_in_queue(1, hours=24)
    print(f"   Кандидат 1 уже в очереди: {is_already}")
    
    print("\n📝 Тест обновления статуса:")
    update_candidate_status(candidate_id, "hired", hired_position="Python Developer", salary=150000)
    updated = get_candidate(candidate_id)
    print(f"   Статус: {updated.get('status')}")
    print(f"   Должность: {updated.get('hired_position')}")
    print(f"   Зарплата: {updated.get('salary')}")
    
    print("\n📦 Тест архивации кандидата...")
    archive_candidate(candidate_id, "test")
    archived_list = get_archived_candidates(limit=10)
    print(f"   В архиве: {len(archived_list)} кандидатов")
    
    print("\n🔄 Тест восстановления из архива...")
    restore_from_archive(candidate_id)
    restored = get_candidate(candidate_id)
    print(f"   Кандидат после восстановления: {'найден' if restored else 'не найден'}")
    
    print("\n📋 Тест сохранения прогресса онбординга...")
    save_onboarding_progress(candidate_id, 3, [{"task": "Задача 1", "completed_at": "2024-01-01"}])
    progress = get_onboarding_progress(candidate_id)
    print(f"   Прогресс: шаг {progress.get('step', 0)}")
    
    print("\n✅ Все тесты пройдены!")
