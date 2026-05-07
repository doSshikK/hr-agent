"""
app/utils/formatters.py
Функции для форматирования данных для вывода пользователю.
"""

from typing import Dict, Any, List


def _safe_list(value) -> List:
    """Гарантирует, что value — список"""
    return value if isinstance(value, list) else []


def format_skills(skills: List[str], limit: int = 5) -> str:

    """ Форматирует список навыков с ограничением """
    skills = _safe_list(skills)
    if not skills:
        return "—"

    result = ", ".join(skills[:limit])
    if len(skills) > limit:
        result += f" +{len(skills) - limit}"
    return result


def format_list_preview(items: List[str], limit: int = 5) -> str:
    """Универсальный форматтер списков"""
    items = _safe_list(items)
    if not items:
        return "—"

    result = ", ".join(items[:limit])
    if len(items) > limit:
        result += f" +{len(items) - limit}"
    return result


def format_candidate_for_display(candidate: Dict[str, Any]) -> str:

    """  Краткое отображение кандидата  """
    skills = _safe_list(candidate.get("skills"))

    output = [
        f"👤 **{candidate.get('name', 'Без имени')}**",
        f"💼 Опыт: {candidate.get('experience_years', 0)} лет"
    ]

    if candidate.get("email"):
        output.append(f"📧 {candidate['email']}")

    if candidate.get("phone"):
        output.append(f"📞 {candidate['phone']}")

    if candidate.get("last_position"):
        output.append(f"📋 {candidate['last_position']}")

    if candidate.get("last_company"):
        output.append(f"🏢 {candidate['last_company']}")

    if skills:
        output.append(f"🛠️ {format_skills(skills, 10)}")

    if candidate.get("match_percent") is not None:
        output.append(f"📊 Совпадение: {candidate['match_percent']}%")

    return "\n".join(output)


def format_candidates_list(candidates: List[Dict[str, Any]], limit: int = 20) -> str:
    """ Список кандидатов """
    if not candidates:
        return "📭 Кандидатов не найдено"

    output = ["📋 **СПИСОК КАНДИДАТОВ**", ""]

    for i, cand in enumerate(candidates[:limit], 1):
        output.append(f"{i}. **#{cand.get('id', '?')}** — {cand.get('name', 'Без имени')}")
        output.append(f"   • Опыт: {cand.get('experience_years', 0)} лет")

        if cand.get("last_position"):
            output.append(f"   • {cand['last_position']}")

        if cand.get("skills"):
            output.append(f"   • {format_skills(cand.get('skills'), 4)}")

        output.append("")

    if len(candidates) > limit:
        output.append(f"... и ещё {len(candidates) - limit} кандидатов")

    return "\n".join(output)


def format_candidate_full_info(candidate: Dict[str, Any]) -> str:
    """  Полная информация о кандидате  """
    return "\n".join([
        f"👤 **{candidate.get('name', 'Без имени')}**",
        f"📧 Email: {candidate.get('email', '—')}",
        f"📞 Телефон: {candidate.get('phone', '—')}",
        f"💼 Опыт: {candidate.get('experience_years', 0)} лет",
        f"📋 Последняя должность: {candidate.get('last_position', '—')}",
        f"🏢 Последняя компания: {candidate.get('last_company', '—')}",
        f"🛠️ Навыки: {format_skills(candidate.get('skills'), 15)}",
        f"📅 Создан: {candidate.get('created_at', '—')}",
    ])


def format_job_for_display(job: Dict[str, Any]) -> str:

    """  Отображение вакансии """
    status_icon = "✅" if job.get("status") == "active" else "📦"

    output = [
        f"💼 **{job.get('title', '—')}**",
        f"📊 Уровень: {job.get('level', '—')}",
        f"💼 Требуемый опыт: {job.get('experience', 0)} лет",
    ]

    if job.get("skills"):
        output.append(f"🛠️ Требуемые навыки: {format_skills(job.get('skills'), 8)}")

    if job.get("description"):
        desc = job["description"][:200]
        if len(job["description"]) > 200:
            desc += "..."
        output.append(f"📝 Описание: {desc}")

    output.append(f"📌 Статус: {status_icon} {job.get('status', '—')}")
    output.append(f"📅 Создана: {job.get('created_at', '—')}")

    return "\n".join(output)


def format_jobs_list(jobs: List[Dict[str, Any]], limit: int = 15) -> str:
    """  Список вакансий """
    if not jobs:
        return "📭 Вакансий не найдено"

    output = ["💼 **СПИСОК ВАКАНСИЙ**", ""]

    for job in jobs[:limit]:
        status_icon = "✅" if job.get("status") == "active" else "📦"
        level_icon = "🟢" if job.get("level") == "junior" else "🟡" if job.get("level") == "middle" else "🔴"

        output.append(
            f"{status_icon} {level_icon} **#{job.get('id')}** — {job.get('title', '—')} ({job.get('level', '—')})"
        )
        output.append(f"   • Опыт: {job.get('experience', 0)} лет")

        if job.get("skills"):
            output.append(f"   • {format_skills(job.get('skills'), 4)}")

        output.append("")

    if len(jobs) > limit:
        output.append(f"... и ещё {len(jobs) - limit} вакансий")

    return "\n".join(output)


def format_job_full_info(job: Dict[str, Any]) -> str:
    """ Полная информация о вакансии """
    status_icon = "✅" if job.get("status") == "active" else "📦"
    
    output = [
        f"💼 **{job.get('title', '—')}**",
        f"📊 Уровень: {job.get('level', '—')}",
        f"💼 Требуемый опыт: {job.get('experience', 0)} лет",
        f"🛠️ Требуемые навыки: {format_skills(job.get('skills'), 20)}",
        f"📌 Статус: {status_icon} {job.get('status', '—')}",
        f"📅 Создана: {job.get('created_at', '—')}",
    ]
    
    if job.get("description"):
        output.insert(4, f"📝 Описание: {job['description']}")
    
    return "\n".join(output)


def format_search_results(results: List[Dict[str, Any]], limit: int = 10) -> str:
    """  Результаты поиска кандидатов """
    if not results:
        return "😕 Кандидаты не найдены."

    output = ["🔍 **РЕЗУЛЬТАТЫ ПОИСКА**", ""]

    for i, cand in enumerate(results[:limit], 1):
        match = cand.get("match_percent", 0)

        if match >= 70:
            emoji = "🏆"
        elif match >= 40:
            emoji = "📊"
        else:
            emoji = "⚠️"

        output.append(f"{emoji} **{i}. {cand.get('name', 'Без имени')}**")
        output.append(f"   • Совпадение: {match}%")
        output.append(f"   • Опыт: {cand.get('experience_years', 0)} лет")

        if cand.get("skills"):
            output.append(f"   • Навыки: {format_skills(cand.get('skills'), 5)}")

        output.append("")

    if len(results) > limit:
        output.append(f"... и ещё {len(results) - limit} кандидатов")

    return "\n".join(output)


def format_match_results_universal(results_or_title, candidates=None, max_skills_display: int = 5) -> str:

    if candidates is None and isinstance(results_or_title, list):
        results = results_or_title
        if not results:
            return "😕 Нет результатов для отображения"
        
        output = []
        for res in results:
            if "error" in res:
                output.append(f"❌ {res['error']}")
                continue
            
            job = res.get("job", {})
            top = res.get("top", [])
            
            output.append(f"\n🎯 Вакансия: {job.get('title', '—')} ({job.get('level', '—')})")
            output.append(f"📊 Найдено кандидатов: {res.get('total_candidates', 0)}, топ-{len(top)}:\n")
            
            for i, r in enumerate(top, 1):
                confidence_emoji = {
                    "excellent": "🏆",
                    "good": "📊",
                    "average": "⚠️",
                    "poor": "❌"
                }.get(r.get("confidence_level", "poor"), "📊")
                
                output.append(f"--- ТОП-{i} {confidence_emoji} ---")
                output.append(f"👤 {r.get('name', 'Без имени')}")
                output.append(f"📧 {r.get('email', 'нет email')}")
                output.append(f"💼 Опыт: {r.get('experience', 0)} лет")
                
                skills = r.get('skills', [])[:max_skills_display]
                if skills:
                    output.append(f"🛠 Навыки: {', '.join(skills)}")
                    if len(r.get('skills', [])) > max_skills_display:
                        output.append(f"   +{len(r['skills']) - max_skills_display} еще")
                
                output.append(f"📊 Матч: {r.get('total_score', 0)}%")
                output.append(f"   • Навыки: {r.get('skills_match', 0)}%")
                output.append(f"   • Опыт: {r.get('experience_match', 0)}%")
                output.append("")
            
            output.append("━" * 70)
        
        return "\n".join(output)
    
    job_title = results_or_title
    if not candidates:
        return f"😕 Подходящих кандидатов для вакансии '{job_title}' не найдено."
    
    output = [f"🎯 **ТОП КАНДИДАТОВ ДЛЯ ВАКАНСИИ: {job_title}**", ""]
    
    for i, cand in enumerate(candidates, 1):
        match = cand.get("match_percent", cand.get("total_score", 0))
        
        output.append(f"{i}. **{cand.get('name', 'Без имени')}** — {match}%")
        output.append(f"   • Опыт: {cand.get('experience_years', cand.get('experience', 0))} лет")
        
        if cand.get("skills"):
            output.append(f"   • Навыки: {format_skills(cand.get('skills'), max_skills_display)}")
        
        output.append("")
    
    return "\n".join(output)


def format_candidates_statistics(stats: Dict[str, Any]) -> str:

    """  Статистика по кандидатам """
    output = [
        "📊 **СТАТИСТИКА КАНДИДАТОВ**",
        "=" * 30,
        f"👥 Всего кандидатов: {stats.get('total', 0)}",
        f"📈 Средний опыт: {stats.get('avg_experience', 0)} лет",
        f"🏆 Максимальный опыт: {stats.get('max_experience', 0)} лет",
        f"🛠️ Уникальных навыков: {stats.get('unique_skills', 0)}",
        "",
        "**🔥 Топ-5 навыков:**"
    ]

    for skill in stats.get("top_skills", [])[:5]:
        output.append(f"   • {skill['skill']}: {skill['count']} кандидатов")

    return "\n".join(output)


def format_jobs_statistics(stats: Dict[str, Any]) -> str:

    """  Статистика по вакансиям  """
    output = [
        "💼 **СТАТИСТИКА ВАКАНСИЙ**",
        "=" * 30,
        f"📋 Всего вакансий: {stats.get('total', 0)}",
        f"✅ Активных: {stats.get('active', 0)}",
        f"📦 Архивных: {stats.get('archived', 0)}",
        f"📊 Средний требуемый опыт: {stats.get('avg_experience_required', 0)} лет",
    ]

    if stats.get("by_level"):
        output.append("")
        output.append("**📊 Распределение по уровням:**")
        for level, count in stats.get("by_level", {}).items():
            level_name = {"junior": "Junior", "middle": "Middle", "senior": "Senior"}.get(level, level)
            output.append(f"   • {level_name}: {count}")

    return "\n".join(output)

def format_overall_statistics(stats: Dict[str, Any]) -> str:

    """ Общая статистика по системе """
    summary = stats.get("summary", {})
    candidates = stats.get("candidates", {})
    jobs = stats.get("jobs", {})
    surveys = stats.get("surveys", {})

    output = [
        "📊 **ОБЩАЯ СТАТИСТИКА HR AGENT**",
        "=" * 35,
        "",
        "👥 **Кандидаты:**",
        f"   • Всего: {summary.get('total_candidates', 0)}",
        f"   • Средний опыт: {candidates.get('avg_experience', 0)} лет",
        f"   • Уникальных навыков: {candidates.get('unique_skills', 0)}",
        "",
        "💼 **Вакансии:**",
        f"   • Всего: {summary.get('total_jobs', 0)}",
        f"   • Активных: {jobs.get('active', 0)}",
        f"   • Средний требуемый опыт: {jobs.get('avg_experience_required', 0)} лет",
        "",
        "📋 **Опросы:**",
        f"   • Всего опросов: {summary.get('total_surveys', 0)}",
        f"   • Всего ответов: {summary.get('total_responses', 0)}",
        f"   • Средний NPS: {surveys.get('avg_nps_score', '—')}",
    ]

    return "\n".join(output)


def format_parsed_resume(result: Dict[str, Any]) -> str:
    """  Результат парсинга резюме  """
    if "error" in result:
        return f"❌ Ошибка: {result['error']}"

    output = [
        "📄 **РЕЗУЛЬТАТ ПАРСИНГА РЕЗЮМЕ**",
        "=" * 40,
        "",
        "👤 **Личные данные:**",
        f"   • Имя: {result.get('name', '—')}",
        f"   • Email: {result.get('email', '—')}",
        f"   • Телефон: {result.get('phone', '—')}",
        "",
        "💼 **Опыт работы:**",
        f"   • Общий опыт: {result.get('experience_years', 0)} лет",
        f"   • Последняя должность: {result.get('last_position', '—')}",
    ]

    if result.get("last_company"):
        output.append(f"   • Последняя компания: {result['last_company']}")

    output.extend([
        "",
        "🛠️ **Навыки:**",
        f"   • {format_skills(result.get('skills'), 15)}",
    ])

    return "\n".join(output)


format_resume_for_display = format_parsed_resume

def format_onboarding_plan_summary(plan: Dict[str, Any]) -> str:

    """ Краткое отображение плана онбординга  """
    output = [
        f"📋 **ПЛАН ОНБОРДИНГА ДЛЯ {plan.get('candidate_name', 'СОТРУДНИКА').upper()}**",
        f"🏢 Отдел: {plan.get('department', '—')}",
        f"📅 Дата начала: {plan.get('start_date_readable', '—')}",
        "",
        "**✅ ОСНОВНЫЕ ЗАДАЧИ (первая неделя):**"
    ]

    for task in plan.get("checklist", [])[:5]:
        output.append(f"   • {task.get('task', '—')}")

    if plan.get("meetings"):
        output.append("")
        output.append("**📅 КЛЮЧЕВЫЕ ВСТРЕЧИ:**")
        for meeting in plan.get("meetings", [])[:3]:
            output.append(f"   • {meeting.get('date_readable', '—')} {meeting.get('time', '—')} — {meeting.get('with', '—')}: {meeting.get('topic', '—')}")

    return "\n".join(output)


def format_test_summary(test: Dict[str, Any]) -> str:

    """  Краткое отображение тестового задания  """
    output = [
        f"📝 **{test.get('title', 'Тестовое задание')}**",
        f"🎯 Направление: {test.get('direction_name', test.get('direction', '—'))}",
        f"📊 Уровень: {test.get('level', '—').upper()}",
        f"⏱ Срок: {test.get('deadline', '—')}",
        "",
        "**📋 ЗАДАЧИ:**"
    ]

    for task in test.get("tasks", [])[:3]:
        output.append(f"   • {task}")

    if len(test.get("tasks", [])) > 3:
        output.append(f"   • ... и ещё {len(test['tasks']) - 3} задач")

    return "\n".join(output)


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ФОРМАТТЕРОВ")
    print("=" * 60)

    print("\n📌 Тест format_skills:")
    skills = ["Python", "Django", "PostgreSQL", "Docker", "Kubernetes", "Redis"]
    print(f"   Навыки: {format_skills(skills, 3)}")
    print(f"   Пустой список: {format_skills([])}")

    print("\n📌 Тест format_candidate_for_display:")
    candidate = {
        "name": "Иванов Иван",
        "email": "ivan@test.com",
        "experience_years": 5,
        "skills": ["Python", "Django", "PostgreSQL"],
        "match_percent": 85
    }
    print(format_candidate_for_display(candidate))

    print("\n📌 Тест format_candidates_list:")
    candidates = [
        {"id": 1, "name": "Иванов Иван", "experience_years": 5, "skills": ["Python"]},
        {"id": 2, "name": "Петров Петр", "experience_years": 3, "skills": ["Java"]},
    ]
    print(format_candidates_list(candidates, limit=2))

    print("\n📌 Тест format_search_results:")
    results = [
        {"name": "Иванов Иван", "match_percent": 85, "experience_years": 5, "skills": ["Python", "Django"]},
        {"name": "Петров Петр", "match_percent": 45, "experience_years": 3, "skills": ["Java"]},
    ]
    print(format_search_results(results, limit=2))

    print("\n📌 Тест format_parsed_resume:")
    parsed = {
        "name": "Сидоров Сидор",
        "email": "sidor@test.com",
        "phone": "+79001234567",
        "experience_years": 4,
        "last_position": "Python Developer",
        "skills": ["Python", "Django", "PostgreSQL"]
    }
    print(format_parsed_resume(parsed))
    
    print("\n📌 Тест format_match_results_universal (оба варианта):")
    
    print("\n   Вариант 1 (job_title + candidates):")
    test_candidates = [
        {"name": "Иванов", "match_percent": 85, "experience_years": 5, "skills": ["Python"]},
        {"name": "Петров", "match_percent": 70, "experience_years": 3, "skills": ["Java"]},
    ]
    print(format_match_results_universal("Python Developer", test_candidates))
    
    print("\n   Вариант 2 (список результатов):")
    test_results = [
        {"job": {"title": "Python Dev", "level": "middle"}, "top": test_candidates, "total_candidates": 10}
    ]
    print(format_match_results_universal(test_results))

    print("\n✅ Все тесты пройдены!")
