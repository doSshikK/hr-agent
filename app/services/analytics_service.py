"""
app/services/analytics_service.py
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.logger import get_logger
from app.db.candidate_db import get_all_candidates, search_candidates
from app.db.jobs_db import get_all_jobs, get_jobs_statistics, get_active_jobs_count
from app.db.survey_db import get_all_surveys, get_responses, analyze_survey_results, get_response_count

logger = get_logger(__name__)


def get_candidates_statistics() -> Dict[str, Any]:

    logger.info("📊 Сбор статистики по кандидатам")
    
    candidates = get_all_candidates(limit=10000)
    
    if not candidates:
        logger.info("Кандидатов в базе нет")
        return {
            "total": 0,
            "avg_experience": 0,
            "max_experience": 0,
            "min_experience": 0,
            "unique_skills": 0,
            "top_skills": [],
            "experience_distribution": {
                "0-1 года": 0,
                "1-3 года": 0,
                "3-5 лет": 0,
                "5-10 лет": 0,
                "10+ лет": 0
            }
        }
    
    total = len(candidates)
    experiences = [c.get("experience_years", 0) or 0 for c in candidates]
    avg_exp = round(sum(experiences) / total, 1) if total else 0
    max_exp = max(experiences) if experiences else 0
    min_exp = min(experiences) if experiences else 0
    
    skill_counts = {}
    for c in candidates:
        for skill in c.get("skills", []):
            if skill:
                skill_lower = skill.lower().strip()
                skill_counts[skill_lower] = skill_counts.get(skill_lower, 0) + 1
    
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_skills_list = [{"skill": s, "count": c} for s, c in top_skills]
    
    exp_distribution = {
        "0-1 года": 0,
        "1-3 года": 0,
        "3-5 лет": 0,
        "5-10 лет": 0,
        "10+ лет": 0
    }
    
    for exp in experiences:
        if exp < 1:
            exp_distribution["0-1 года"] += 1
        elif exp < 3:
            exp_distribution["1-3 года"] += 1
        elif exp < 5:
            exp_distribution["3-5 лет"] += 1
        elif exp < 10:
            exp_distribution["5-10 лет"] += 1
        else:
            exp_distribution["10+ лет"] += 1
    
    logger.info(f"✅ Статистика собрана: {total} кандидатов, средний опыт {avg_exp} лет")
    
    return {
        "total": total,
        "avg_experience": avg_exp,
        "max_experience": max_exp,
        "min_experience": min_exp,
        "unique_skills": len(skill_counts),
        "top_skills": top_skills_list,
        "experience_distribution": exp_distribution
    }


def get_candidates_by_skill(skill: str) -> List[Dict[str, Any]]:

    logger.info(f"🔍 Поиск кандидатов по навыку: {skill}")
    
    skill_lower = skill.lower().strip()
    candidates = get_all_candidates(limit=10000)
    
    result = []
    for c in candidates:
        c_skills = [s.lower().strip() for s in c.get("skills", []) if s]
        if skill_lower in c_skills:
            result.append(c)
    
    logger.info(f"✅ Найдено кандидатов с навыком '{skill}': {len(result)}")
    return result


def get_candidates_by_experience_range(min_years: int, max_years: int) -> List[Dict[str, Any]]:

    logger.info(f"🔍 Поиск кандидатов с опытом {min_years}-{max_years} лет")
    
    candidates = get_all_candidates(limit=10000)
    
    result = []
    for c in candidates:
        exp = c.get("experience_years", 0) or 0
        if min_years <= exp <= max_years:
            result.append(c)
    
    logger.info(f"✅ Найдено кандидатов: {len(result)}")
    return result


def get_jobs_statistics_full() -> Dict[str, Any]:

    logger.info("📊 Сбор статистики по вакансиям")
    
    jobs = get_all_jobs(active_only=False)
    
    if not jobs:
        logger.info("Вакансий в базе нет")
        return {
            "total": 0,
            "active": 0,
            "archived": 0,
            "by_level": {},
            "avg_experience_required": 0,
            "top_skills": []
        }
    
    total = len(jobs)
    active = sum(1 for j in jobs if j.get("status") == "active")
    archived = total - active
    
    by_level = {
        "junior": 0,
        "middle": 0,
        "senior": 0
    }
    for j in jobs:
        level = j.get("level", "middle")
        if level in by_level:
            by_level[level] += 1
    
    experiences = [j.get("experience", 0) or 0 for j in jobs]
    avg_exp = round(sum(experiences) / total, 1) if total else 0
    
    skill_counts = {}
    for j in jobs:
        for skill in j.get("skills", []):
            if skill:
                skill_lower = skill.lower().strip()
                skill_counts[skill_lower] = skill_counts.get(skill_lower, 0) + 1
    
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_skills_list = [{"skill": s, "count": c} for s, c in top_skills]
    
    logger.info(f"✅ Статистика собрана: {total} вакансий, активных {active}")
    
    return {
        "total": total,
        "active": active,
        "archived": archived,
        "by_level": by_level,
        "avg_experience_required": avg_exp,
        "top_skills": top_skills_list
    }


def get_jobs_by_level(level: str) -> List[Dict[str, Any]]:

    logger.info(f"🔍 Поиск вакансий уровня: {level}")
    
    jobs = get_all_jobs(active_only=False)
    result = [j for j in jobs if j.get("level") == level]
    
    logger.info(f"✅ Найдено вакансий уровня {level}: {len(result)}")
    return result


def get_active_jobs() -> List[Dict[str, Any]]:

    logger.debug("🔍 Получение активных вакансий")
    return get_all_jobs(active_only=True)


def get_surveys_statistics() -> Dict[str, Any]:

    logger.info("📊 Сбор статистики по опросам")
    
    surveys = get_all_surveys(active_only=False)
    
    if not surveys:
        logger.info("Опросов в базе нет")
        return {
            "total": 0,
            "active": 0,
            "closed": 0,
            "by_type": {"nps": 0, "pulse": 0},
            "total_responses": 0,
            "avg_nps_score": None
        }
    
    total = len(surveys)
    active = sum(1 for s in surveys if s.get("status") == "active")
    closed = total - active
    
    by_type = {"nps": 0, "pulse": 0}
    for s in surveys:
        s_type = s.get("type", "nps")
        if s_type in by_type:
            by_type[s_type] += 1
    
    total_responses = 0
    nps_scores = []
    
    for s in surveys:
        response_count = get_response_count(s["id"])
        total_responses += response_count
        
        if s.get("type") == "nps" and response_count > 0:
            analysis = analyze_survey_results(s["id"])
            if "nps_score" in analysis and analysis["nps_score"] is not None:
                nps_scores.append(analysis["nps_score"])
    
    avg_nps = round(sum(nps_scores) / len(nps_scores), 1) if nps_scores else None
    
    logger.info(f"✅ Статистика собрана: {total} опросов, {total_responses} ответов")
    
    return {
        "total": total,
        "active": active,
        "closed": closed,
        "by_type": by_type,
        "total_responses": total_responses,
        "avg_nps_score": avg_nps
    }


def get_survey_details(survey_id: int) -> Dict[str, Any]:

    logger.info(f"🔍 Получение деталей опроса ID: {survey_id}")
    
    from app.db.survey_db import get_survey
    
    survey = get_survey(survey_id)
    if not survey:
        logger.warning(f"Опрос с ID {survey_id} не найден")
        return {"error": f"Опрос с ID {survey_id} не найден"}
    
    analysis = analyze_survey_results(survey_id)
    
    return {
        "survey": survey,
        "analysis": analysis
    }


def get_overall_statistics() -> Dict[str, Any]:

    logger.info("📊 Сбор общей статистики")
    
    candidates_stats = get_candidates_statistics()
    jobs_stats = get_jobs_statistics_full()
    surveys_stats = get_surveys_statistics()
    
    result = {
        "candidates": candidates_stats,
        "jobs": jobs_stats,
        "surveys": surveys_stats,
        "summary": {
            "total_candidates": candidates_stats["total"],
            "total_jobs": jobs_stats["total"],
            "active_jobs": jobs_stats["active"],
            "total_surveys": surveys_stats["total"],
            "total_responses": surveys_stats["total_responses"],
            "avg_experience": candidates_stats["avg_experience"]
        }
    }
    
    logger.info(f"✅ Общая статистика: {candidates_stats['total']} кандидатов, {jobs_stats['total']} вакансий")
    
    return result


def get_quick_stats() -> Dict[str, Any]:

    logger.debug("📊 Сбор краткой статистики")
    
    candidates = get_all_candidates(limit=10000)
    jobs = get_all_jobs(active_only=False)
    active_jobs = get_active_jobs_count()
    surveys = get_all_surveys(active_only=False)
    
    total_responses = 0
    for s in surveys:
        total_responses += get_response_count(s["id"])
    
    return {
        "total_candidates": len(candidates),
        "total_jobs": len(jobs),
        "active_jobs": active_jobs,
        "total_surveys": len(surveys),
        "total_responses": total_responses,
        "generated_at": datetime.now().isoformat()
    }


def export_candidates_to_json(file_path: str) -> bool:

    logger.info(f"💾 Экспорт кандидатов в JSON: {file_path}")
    
    candidates = get_all_candidates(limit=10000)
    
    data = {
        "exported_at": datetime.now().isoformat(),
        "total": len(candidates),
        "candidates": candidates
    }
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ Кандидаты экспортированы в {file_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при экспорте кандидатов: {e}")
        return False


def export_jobs_to_json(file_path: str) -> bool:

    logger.info(f"💾 Экспорт вакансий в JSON: {file_path}")
    
    jobs = get_all_jobs(active_only=False)
    
    data = {
        "exported_at": datetime.now().isoformat(),
        "total": len(jobs),
        "jobs": jobs
    }
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ Вакансии экспортированы в {file_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при экспорте вакансий: {e}")
        return False


def export_surveys_to_json(file_path: str) -> bool:

    logger.info(f"💾 Экспорт опросов в JSON: {file_path}")
    
    surveys = get_all_surveys(active_only=False)
    
    surveys_data = []
    for s in surveys:
        responses = get_responses(s["id"])
        surveys_data.append({
            "survey": s,
            "responses": responses,
            "analysis": analyze_survey_results(s["id"])
        })
    
    data = {
        "exported_at": datetime.now().isoformat(),
        "total": len(surveys),
        "surveys": surveys_data
    }
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ Опросы экспортированы в {file_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при экспорте опросов: {e}")
        return False


def export_full_report(file_path: str) -> bool:

    logger.info(f"💾 Экспорт полного отчёта: {file_path}")
    
    stats = get_overall_statistics()
    quick_stats = get_quick_stats()
    
    data = {
        "exported_at": datetime.now().isoformat(),
        "statistics": stats,
        "quick_stats": quick_stats
    }
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ Полный отчёт экспортирован в {file_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при экспорте отчёта: {e}")
        return False


def get_top_skills(limit: int = 10) -> List[Dict[str, Any]]:

    logger.debug(f"🔍 Получение топ-{limit} навыков")
    
    candidates = get_all_candidates(limit=10000)
    
    skill_counts = {}
    for c in candidates:
        for skill in c.get("skills", []):
            if skill:
                skill_lower = skill.lower().strip()
                skill_counts[skill_lower] = skill_counts.get(skill_lower, 0) + 1
    
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    return [{"skill": s, "count": c} for s, c in top_skills]


def get_experience_distribution() -> Dict[str, int]:

    logger.debug("📊 Получение распределения по опыту")
    
    candidates = get_all_candidates(limit=10000)
    
    distribution = {
        "0-1 года": 0,
        "1-3 года": 0,
        "3-5 лет": 0,
        "5-10 лет": 0,
        "10+ лет": 0
    }
    
    for c in candidates:
        exp = c.get("experience_years", 0) or 0
        if exp < 1:
            distribution["0-1 года"] += 1
        elif exp < 3:
            distribution["1-3 года"] += 1
        elif exp < 5:
            distribution["3-5 лет"] += 1
        elif exp < 10:
            distribution["5-10 лет"] += 1
        else:
            distribution["10+ лет"] += 1
    
    return distribution


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ANALYTICS_SERVICE")
    print("=" * 60)
    
    print("\n📊 Быстрая статистика:")
    quick = get_quick_stats()
    print(f"   Кандидатов: {quick['total_candidates']}")
    print(f"   Вакансий: {quick['total_jobs']}")
    print(f"   Активных вакансий: {quick['active_jobs']}")
    print(f"   Опросов: {quick['total_surveys']}")
    print(f"   Ответов: {quick['total_responses']}")
    
    print("\n📊 Статистика по кандидатам:")
    candidates_stats = get_candidates_statistics()
    print(f"   Всего: {candidates_stats['total']}")
    print(f"   Средний опыт: {candidates_stats['avg_experience']} лет")
    print(f"   Уникальных навыков: {candidates_stats['unique_skills']}")
    
    print("\n📊 Топ навыков:")
    top_skills = get_top_skills(5)
    for skill in top_skills:
        print(f"   • {skill['skill']}: {skill['count']}")
    
    print("\n📊 Распределение по опыту:")
    exp_dist = get_experience_distribution()
    for range_name, count in exp_dist.items():
        print(f"   • {range_name}: {count}")
    
    print("\n📊 Статистика по вакансиям:")
    jobs_stats = get_jobs_statistics_full()
    print(f"   Всего: {jobs_stats['total']}")
    print(f"   Активных: {jobs_stats['active']}")
    print(f"   Средний опыт: {jobs_stats['avg_experience_required']} лет")
    
    print("\n📊 Общая статистика:")
    overall = get_overall_statistics()
    summary = overall.get('summary', {})
    print(f"   Всего кандидатов: {summary.get('total_candidates', 0)}")
    print(f"   Всего вакансий: {summary.get('total_jobs', 0)}")
    
    print("\n✅ Analytics сервис готов к работе!")
