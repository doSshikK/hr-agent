"""
app/services/job_matcher.py
Matching кандидатов под вакансии (ядро)
"""

import argparse
import logging
from typing import List, Optional, Dict, Any

from app.db.jobs_db import get_job, get_all_jobs
from app.db.candidate_db import get_all_candidates as get_all_candidates_full
from app.db.candidate_db import search_candidates as db_search_candidates
from app.core.logger import get_logger

logger = get_logger(__name__)


SKILL_SYNONYMS = {
    "py": "python",
    "python3": "python",
    "python 3": "python",
    "js": "javascript",
    "es6": "javascript",
    "ts": "typescript",
    "c++": "cpp",
    "cpp": "cpp",
    "c#": "csharp",
    "csharp": "csharp",
    
    "drf": "django",
    "django rest": "django",
    "flask restful": "flask",
    
    "pg": "postgresql",
    "postgres": "postgresql",
    "mongo": "mongodb",
    
    "k8s": "kubernetes",
    "gke": "kubernetes",
    
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
}


def normalize_skill(skill: str) -> str:

    """ Нормализует название навыка """
    if not skill:
        return ""
    cleaned = skill.lower().strip()
    return SKILL_SYNONYMS.get(cleaned, cleaned)


def normalize_skills_list(skills: List[str]) -> List[str]:
    """Нормализует список навыков"""
    return [normalize_skill(s) for s in skills if s]


def normalize_skills_set(skills: List[str]) -> set:
    """Нормализует список навыков и возвращает множество"""
    return set(normalize_skills_list(skills))


def calculate_skills_match(job_skills: set, candidate_skills: set) -> tuple:

    """  Рассчитывает совпадение навыков  """
    if not job_skills:
        return 0.5, [], 50.0, "average"
    
    if not candidate_skills:
        return 0.0, [], 0.0, "poor"
    
    matched = job_skills & candidate_skills
    skills_match = len(matched) / len(job_skills)
    
    confidence = (len(matched) / len(job_skills)) * 100
    
    if confidence >= 80:
        confidence_level = "excellent"
    elif confidence >= 60:
        confidence_level = "good"
    elif confidence >= 40:
        confidence_level = "average"
    else:
        confidence_level = "poor"
    
    return skills_match, list(matched), confidence, confidence_level


def calculate_experience_match(candidate_exp: int, required_exp: int) -> float:
    
    """ Рассчитывает совпадение по опыту  """
    if required_exp <= 0:
        return 1.0
    
    if candidate_exp <= 0:
        return 0.0
    
    experience_match = min(candidate_exp / required_exp, 1.2)
    return min(experience_match, 1.0)


def calculate_education_match(candidate: Dict[str, Any]) -> float:

    """ Рассчитывает совпадение по образованию """
    return 1.0


def calculate_score(
    skills_match: float,
    experience_match: float,
    education_match: float,
    weight_skills: float = 0.5,
    weight_experience: float = 0.3,
    weight_education: float = 0.2
) -> float:

    total_weight = weight_skills + weight_experience + weight_education
    
    if total_weight > 0:
        weight_skills /= total_weight
        weight_experience /= total_weight
        weight_education /= total_weight
    
    score = (
        skills_match * weight_skills +
        experience_match * weight_experience +
        education_match * weight_education
    ) * 100
    
    return round(score, 2)


def match_candidates_to_job(
    job: Dict[str, Any],
    candidates: List[Dict[str, Any]] = None,
    weight_skills: float = 0.5,
    weight_experience: float = 0.3,
    weight_education: float = 0.2
) -> List[Dict[str, Any]]:

    logger.info(f"🔄 Формализованный скоринг для вакансии: {job.get('title')}")
    
    if not job.get('skills'):
        logger.warning(f"⚠️ Вакансия '{job.get('title')}' не имеет требуемых навыков! Результаты могут быть неточными.")
    
    if candidates is None:
        logger.info("   Кандидаты не переданы, получаем через search_candidates()")
        candidates = db_search_candidates(
            query_skills=job.get('skills', []),
            min_experience=job.get('experience'),
            position=job.get('title'),
            min_match_percent=0  # берём всех кандидатов
        )
        logger.info(f"   Получено кандидатов: {len(candidates)}")
    
    logger.info(f"   Веса: навыки={weight_skills:.2f}, опыт={weight_experience:.2f}, образование={weight_education:.2f}")
    
    job_skills = normalize_skills_set(job.get('skills', []))
    required_exp = max(job.get('experience', 0), 1)  # избегаем деления на 0
    
    results = []
    
    for cand in candidates:
        cand_skills = normalize_skills_set(cand.get('skills', []))
        cand_exp = max(cand.get('experience_years', 0), 0)
        
        skills_match, matched_skills, confidence, confidence_level = calculate_skills_match(
            job_skills, cand_skills
        )
        
        experience_match = calculate_experience_match(cand_exp, required_exp)
        
        education_match = calculate_education_match(cand)
        
        total_score = calculate_score(
            skills_match, experience_match, education_match,
            weight_skills, weight_experience, weight_education
        )
        
        results.append({
            "id": cand.get("id"),
            "name": cand.get("name", "Без имени"),
            "email": cand.get("email", "нет email"),
            "skills": list(cand_skills),
            "experience": cand_exp,
            "skills_match": round(skills_match * 100, 2),
            "experience_match": round(experience_match * 100, 2),
            "education_match": round(education_match * 100, 2),
            "total_score": total_score,
            "match_percent": total_score,  # для совместимости с форматерами
            "matched_skills": matched_skills,
            "confidence": round(confidence, 2),
            "confidence_level": confidence_level
        })
    
    results.sort(key=lambda x: x["total_score"], reverse=True)
    
    if results:
        logger.info(f"✅ Топ-3 скоринга:")
        for i, r in enumerate(results[:3], 1):
            logger.info(f"   {i}. {r['name']}: {r['total_score']}% (навыки: {r['skills_match']}%)")
    
    return results


def match_candidates_by_job_id(job_id: int, top_n: int = 5) -> Dict[str, Any]:

    """ Подбирает кандидатов для вакансии по ID  """
    logger.info(f"🔍 Matching для вакансии ID: {job_id}")
    
    job = get_job(job_id)
    if not job:
        return {"error": f"Вакансия с ID {job_id} не найдена"}
    
    scored_candidates = match_candidates_to_job(job, None, 0.5, 0.3, 0.2)
    
    return {
        "job": job,
        "top_candidates": scored_candidates[:top_n],
        "total_candidates": len(scored_candidates)
    }


def match_by_job_ids(
    job_ids: List[int],
    top_n: int = 5,
    weight_skills: float = 0.5,
    weight_experience: float = 0.3,
    weight_education: float = 0.2,
    max_skills: int = 8
) -> List[Dict[str, Any]]:

    """ Подбирает кандидатов для списка вакансий """
    logger.info(f"🔍 Matching по вакансиям: {job_ids}")
    
    jobs = [get_job(jid) for jid in job_ids]
    candidates = get_all_candidates_full()
    results = []

    for job in jobs:
        if not job:
            logger.warning(f"Вакансия не найдена: {job_ids}")
            results.append({"job_id": None, "error": "Вакансия не найдена"})
            continue

        logger.info(f"📊 Оценка кандидатов для вакансии: {job.get('title')}")
        scored = match_candidates_to_job(
            job, candidates,
            weight_skills, weight_experience, weight_education
        )
        top_results = scored[:top_n]

        for r in top_results:
            if 'skills' in r and len(r['skills']) > max_skills:
                r['skills'] = r['skills'][:max_skills]

        results.append({
            "job": job,
            "top": top_results,
            "total_candidates": len(scored)
        })

    return results


def format_job_matcher_result(result: Dict[str, Any], max_skills_display: int = 5) -> str:

    """ Форматирует результат matching для вывода """
    if "error" in result:
        return f"❌ {result['error']}"

    job = result["job"]
    top = result["top"]
    
    output = []
    output.append(f"\n🎯 Вакансия: {job['title']} ({job['level']})")
    output.append(f"📊 Найдено кандидатов: {result['total_candidates']}, топ-{len(top)}:\n")

    for i, r in enumerate(top, 1):
        confidence_emoji = {
            "excellent": "🏆",
            "good": "📊",
            "average": "⚠️",
            "poor": "❌"
        }.get(r.get("confidence_level", "poor"), "📊")
        
        output.append(f"--- ТОП-{i} {confidence_emoji} ---")
        output.append(f"👤 {r['name']}")
        output.append(f"📧 {r['email']}")
        output.append(f"💼 Опыт: {r['experience']} лет")
        
        skills_display = r.get('skills', [])[:max_skills_display]
        if skills_display:
            output.append(f"🛠 Навыки: {', '.join(skills_display)}")
            if len(r.get('skills', [])) > max_skills_display:
                output.append(f"   +{len(r['skills']) - max_skills_display} еще")
        
        output.append(f"📊 Матч: {r.get('total_score', r.get('match_percent', 0))}%")
        output.append(f"   • Навыки: {r['skills_match']}%")
        output.append(f"   • Опыт: {r['experience_match']}%")
        output.append(f"   • Уверенность: {r['confidence']}% ({r.get('confidence_level', '—')})")
        output.append("")

    return "\n".join(output)


def format_match_results(results: List[Dict[str, Any]], max_skills_display: int = 5) -> str:

    """ Форматирует несколько результатов matching """
    output = []
    for res in results:
        output.append(format_job_matcher_result(res, max_skills_display))
        output.append("\n" + "━" * 70)
    return "\n".join(output)
