"""
app/services/candidate_service.py
Сервис для работы с кандидатами
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings
from app.core.logger import get_logger
from app.db.candidate_db import (
    save_candidate,
    get_candidate,
    get_all_candidates,
    delete_candidate,
    restore_candidate,
    search_candidates, 
    get_connection
)
from app.utils.file_parser import parse_resume
from app.models.candidate import Candidate
from app.utils.formatters import format_candidate_for_display, format_candidates_list

logger = get_logger(__name__)


def add_candidate_from_resume(
    file_path: str,
    auto_save: bool = False
) -> Dict[str, Any]:

    logger.info(f"📄 Обработка резюме из файла: {file_path}")
    
    parsed_data = parse_resume(file_path)
    
    if "error" in parsed_data:
        logger.error(f"Ошибка парсинга: {parsed_data['error']}")
        return {
            "success": False,
            "error": parsed_data["error"],
            "parsed_data": None
        }
    
    exists, existing = check_candidate_exists(parsed_data)
    
    result = {
        "success": True,
        "parsed_data": parsed_data,
        "exists": exists,
        "existing_candidate": existing if exists else None
    }
    
    if auto_save and not exists:
        candidate_id = save_candidate(parsed_data, file_path)
        result["saved_id"] = candidate_id
        logger.info(f"✅ Кандидат автоматически сохранён с ID: {candidate_id}")
    elif auto_save and exists:
        logger.warning(f"Кандидат уже существует (ID: {existing['id']}), автосохранение пропущено")
        result["error"] = "Кандидат уже существует, сохранение пропущено"
    
    return result


def check_candidate_exists(candidate_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    
    """ Проверяет, существует ли кандидат в базе данных """
    email = candidate_data.get("email")
    name = candidate_data.get("name")
    file_hash = candidate_data.get("file_hash")
    
    candidates = get_all_candidates(limit=10000)
    
    logger.debug(f"🔍 Проверка кандидата: email={email}, name={name}")
    
    if email:
        email_lower = email.lower().strip()
        for c in candidates:
            if c.get("email") and c.get("email").lower().strip() == email_lower:
                logger.info(f"✅ Найден по email: {c.get('name')} (ID: {c.get('id')})")
                return True, c
    
    if name:
        name_lower = name.lower().strip()
        for c in candidates:
            if c.get("name") and c.get("name").lower().strip() == name_lower:
                logger.info(f"✅ Найден по имени: {c.get('name')} (ID: {c.get('id')})")
                return True, c
    
    if file_hash:
        for c in candidates:
            if c.get("file_hash") == file_hash:
                logger.info(f"✅ Найден по хешу файла: {c.get('name')} (ID: {c.get('id')})")
                return True, c
    
    logger.debug("❌ Кандидат не найден")
    return False, None


def save_candidate_from_parsed(
    parsed_data: Dict[str, Any],
    file_path: Optional[str] = None,
    force_update: bool = False
) -> int:
    """ Сохраняет распарсенного кандидата в базу  """
    logger.info(f"💾 Сохранение кандидата из распарсенных данных, force_update={force_update}")
    
    exists, existing = check_candidate_exists(parsed_data)
    
    if exists and not force_update:
        logger.warning(f"Кандидат уже существует (ID: {existing['id']}), пропускаем")
        return existing["id"]
    
    candidate_id = save_candidate(parsed_data, file_path)
    action = "обновлён" if exists else "добавлен"
    logger.info(f"✅ Кандидат {action} с ID: {candidate_id}")
    
    return candidate_id


def get_candidate_by_id(candidate_id: int) -> Optional[Candidate]:

    """ Возвращает кандидата по ID в виде модели Candidate """
    logger.debug(f"🔍 Получение кандидата по ID: {candidate_id}")
    data = get_candidate(candidate_id)
    if data:
        return Candidate.from_db_row(data)
    logger.warning(f"Кандидат с ID {candidate_id} не найден")
    return None


def get_all_candidates_as_models(limit: int = 100, offset: int = 0) -> List[Candidate]:

    """ Возвращает всех кандидатов в виде списка моделей Candidate  """
    logger.debug(f"📋 Получение всех кандидатов (limit={limit}, offset={offset})")
    candidates_data = get_all_candidates(limit=limit, offset=offset)
    return [Candidate.from_db_row(c) for c in candidates_data]


def update_candidate(candidate_id: int, updates: Dict[str, Any]) -> bool:
   
    """ Обновляет данные кандидата  """
    logger.info(f"✏️ Обновление кандидата ID: {candidate_id}, поля: {list(updates.keys())}")
    
    existing = get_candidate(candidate_id)
    if not existing:
        logger.error(f"Кандидат с ID {candidate_id} не найден")
        return False
    
    updated_data = {**existing, **updates}
    updated_data["id"] = candidate_id
    
    save_candidate(updated_data, existing.get("file_name"))
    
    logger.info(f"✅ Кандидат ID {candidate_id} обновлён")
    return True


def remove_candidate(candidate_id: int, soft_delete: bool = True) -> bool:
    
    """ Удаляет кандидата   """
    logger.info(f"🗑️ Удаление кандидата ID: {candidate_id}, soft_delete={soft_delete}")
    
    if soft_delete:
        return delete_candidate(candidate_id)
    else:
        with get_connection() as conn:
            conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
            conn.commit()
            logger.info(f"✅ Кандидат ID {candidate_id} полностью удалён из БД")
            return True

def search_candidates_by_criteria(
    skills: List[str] = None,
    min_experience: int = None,
    position: str = None,
    query_text: str = None,
    min_match_percent: int = None,
    top_n: int = None
) -> List[Dict[str, Any]]:
    """
    Универсальный поиск кандидатов с комбинацией условий
    """
    if min_match_percent is None:
        min_match_percent = settings.min_match_percent
    
    logger.info(f"🔍 Поиск: навыки={skills}, опыт={min_experience}, должность={position}, текст={query_text}")
    
    combined_query_text = query_text
    if position and not combined_query_text:
        combined_query_text = position
    elif position and combined_query_text:
        combined_query_text = f"{position} {combined_query_text}"
    
    results = search_candidates(
        query_skills=skills or [],
        min_experience=min_experience,
        position=position,
        query_text=combined_query_text,
        min_match_percent=min_match_percent
    )
    
    if top_n and top_n > 0:
        results = results[:top_n]
    
    logger.info(f"✅ Найдено кандидатов: {len(results)}")
    return results

def get_candidate_statistics() -> Dict[str, Any]:

    """ Возвращает статистику по кандидатам  """
    logger.debug("📊 Сбор статистики по кандидатам")
    
    candidates = get_all_candidates(limit=10000)
    
    if not candidates:
        logger.debug("Кандидатов нет")
        return {
            "total": 0,
            "avg_experience": 0,
            "max_experience": 0,
            "unique_skills": 0,
            "top_skills": []
        }
    
    total = len(candidates)
    total_exp = sum(c.get("experience_years", 0) or 0 for c in candidates)
    avg_exp = round(total_exp / total, 1) if total else 0
    max_exp = max(c.get("experience_years", 0) or 0 for c in candidates)
    
    skill_counts = {}
    for c in candidates:
        for skill in c.get("skills", []):
            if skill:
                skill_lower = skill.lower().strip()
                skill_counts[skill_lower] = skill_counts.get(skill_lower, 0) + 1
    
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_skills_list = [{"skill": s, "count": c} for s, c in top_skills]
    
    logger.debug(f"Статистика: {total} кандидатов, средний опыт {avg_exp} лет")
    
    return {
        "total": total,
        "avg_experience": avg_exp,
        "max_experience": max_exp,
        "unique_skills": len(skill_counts),
        "top_skills": top_skills_list
    }


def validate_resume_file(file_path: str) -> Dict[str, Any]:
    """ Проверяет файл резюме перед обработкой """
    logger.debug(f"🔍 Валидация файла резюме: {file_path}")
    
    path = Path(file_path)
    
    if not path.exists():
        logger.error(f"Файл не найден: {file_path}")
        return {"valid": False, "error": f"Файл не найден: {file_path}"}
    
    ext = path.suffix.lower()
    if ext not in settings.supported_file_extensions:
        logger.error(f"Неподдерживаемый формат: {ext}")
        return {
            "valid": False,
            "error": f"Неподдерживаемый формат: {ext}. Поддерживаются: {', '.join(settings.supported_file_extensions)}"
        }
    
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > settings.max_file_size_mb:
        logger.error(f"Файл слишком большой: {file_size_mb:.1f} МБ")
        return {
            "valid": False,
            "error": f"Файл слишком большой: {file_size_mb:.1f} МБ (макс. {settings.max_file_size_mb} МБ)"
        }
    
    logger.debug(f"Файл валиден, размер: {file_size_mb:.2f} МБ")
    return {"valid": True, "file_size_mb": round(file_size_mb, 2)}


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ СЕРВИСА CANDIDATE_SERVICE")
    print("=" * 60)
    
    print("\n📊 Статистика кандидатов:")
    stats = get_candidate_statistics()
    print(f"   Всего: {stats['total']}")
    print(f"   Средний опыт: {stats['avg_experience']} лет")
    print(f"   Уникальных навыков: {stats['unique_skills']}")
    
    print("\n📋 Список кандидатов:")
    candidates = get_all_candidates(limit=10)
    print(format_candidates_list(candidates, limit=5))
    
    print("\n✅ Сервис готов к работе!")
