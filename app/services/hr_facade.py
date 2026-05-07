"""
app/services/hr_facade.py
Facade для унификации доступа к HR сервисам
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.core.logger import get_logger
from app.services.candidate_service import (
    add_candidate_from_resume,
    get_candidate_by_id,
    get_all_candidates_as_models,
    update_candidate,
    remove_candidate,
    search_candidates_by_criteria,
    get_candidate_statistics
)
from app.services.test_generator import generate_test as generate_test_task, format_test
from app.services.onboarding_generator import generate_onboarding_plan as create_onboarding_plan, format_onboarding_plan
from app.db.jobs_db import (
    create_job as add_job,
    get_job as get_job_by_id,
    get_all_jobs as get_all_jobs_list,
    get_all_jobs_with_status,
    update_job as update_job_info,
    delete_job as remove_job,
    archive_job as archive_job_by_id,
    activate_job as activate_job_by_id,
    search_jobs as search_jobs_by_criteria,
    get_jobs_statistics
)
from app.services.analytics_service import (
    get_overall_statistics,
    get_quick_stats,
    export_candidates_to_json,
    export_jobs_to_json
)
from app.services.job_matcher import match_candidates_to_job, match_by_job_ids
from app.utils.file_parser import parse_resume
from app.utils.formatters import (
    format_candidate_for_display,
    format_candidates_list,
    format_candidate_full_info,
    format_job_for_display,
    format_jobs_list,
    format_search_results
)

from app.db.candidate_db import (
    get_all_candidates,
    save_candidate as db_save_candidate,
    get_candidate,
    get_candidate_by_telegram_id,
    get_all_candidates_full as db_get_all_candidates_full,
    get_resume_from_db as db_get_resume_from_db,
    has_resume_in_db as db_has_resume_in_db,
    update_candidate_status,
    search_candidates as db_search_candidates,
    archive_candidate as db_archive_candidate,
    restore_from_archive as db_restore_from_archive,
    get_archived_candidates as db_get_archived_candidates,
    is_candidate_archived as db_is_candidate_archived,
    delete_archived_candidate as db_delete_archived_candidate,
    delete_all_archived_candidates as db_delete_all_archived_candidates,
    is_candidate_already_in_queue,
    add_to_notification_queue as db_add_to_notification_queue,
    save_onboarding_progress as db_save_onboarding_progress,
    get_onboarding_progress as db_get_onboarding_progress,
    start_onboarding as db_start_onboarding,
    complete_onboarding as db_complete_onboarding,
)
from app.db.survey_db import (
    delete_survey as db_delete_survey,
    delete_all_surveys as db_delete_all_surveys,
    create_survey as db_create_survey,
    analyze_survey_results,
    get_all_surveys,
    get_responses,
    get_survey,
    submit_response as db_submit_response,
    get_response_count as db_get_response_count,
)
from app.utils.charts import create_nps_chart as make_nps_chart, create_pulse_chart as make_pulse_chart

from app.db.interview_db import (
    add_slot as db_add_slot,
    get_all_slots as db_get_all_slots,
    get_slots_by_hr as db_get_slots_by_hr,
    get_slots_by_date as db_get_slots_by_date,
    book_slot as db_book_slot,
    cancel_booking as db_cancel_booking,
    cancel_booking_by_candidate as db_cancel_booking_by_candidate,
    get_candidate_slot as db_get_candidate_slot,
    get_slot_by_id as db_get_slot_by_id,
    delete_slot as db_delete_slot,
    delete_free_slots_by_date as db_delete_free_slots_by_date,
    generate_slots_for_date as db_generate_slots_for_date,
    get_free_slots_grouped_by_date as db_get_free_slots_grouped_by_date,
    get_interview_settings as db_get_interview_settings,
    is_date_fully_booked as db_is_date_fully_booked,
    has_free_slots as db_has_free_slots,
)
from app.db.jobs_db import create_job as db_create_job, update_job as db_update_job
from app.db.conversation_db import (
    save_conversation_message as db_save_conversation_message,
    get_recent_conversation_history as db_get_recent_conversation_history,
)

logger = get_logger(__name__)


class HRAgentFacade:
    
    
    @staticmethod
    def parse_resume(file_path: str) -> Dict[str, Any]:
        """Парсит резюме из файла"""
        logger.info(f"Facade: парсинг резюме {file_path}")
        return parse_resume(file_path)

    @staticmethod
    def save_conversation_message(
        telegram_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Сохраняет сообщение диалога для LLM-контекста."""
        db_save_conversation_message(telegram_id, role, content, metadata)

    @staticmethod
    def get_recent_conversation_history(telegram_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """Возвращает последние сообщения пользователя для LLM-контекста."""
        return db_get_recent_conversation_history(telegram_id, limit)
    
    @staticmethod
    def add_candidate(file_path: str, auto_save: bool = False) -> Dict[str, Any]:
        """Добавляет кандидата из резюме"""
        logger.info(f"Facade: добавление кандидата из {file_path}")
        return add_candidate_from_resume(file_path, auto_save)
    
    @staticmethod
    def get_candidate(candidate_id: int) -> Optional[Dict[str, Any]]:
        """Получает кандидата по ID"""
        logger.debug(f"Facade: получение кандидата {candidate_id}")
        candidate = get_candidate_by_id(candidate_id)
        return candidate.to_dict() if candidate else None
    
    @staticmethod
    def get_all_candidates(limit: int = 1000) -> List[Dict[str, Any]]:
        """Возвращает всех кандидатов из БД в виде словарей."""
        logger.debug(f"Facade: получение всех кандидатов (limit={limit})")
        return get_all_candidates(limit=limit)

    @staticmethod
    def get_all_candidates_dict(limit: int = 1000) -> List[Dict[str, Any]]:
        """Псевдоним get_all_candidates — для обратной совместимости."""
        return HRAgentFacade.get_all_candidates(limit=limit)
    
    @staticmethod
    def update_candidate(candidate_id: int, updates: Dict[str, Any]) -> bool:
        """Обновляет данные кандидата"""
        logger.info(f"Facade: обновление кандидата {candidate_id}")
        return update_candidate(candidate_id, updates)
    
    @staticmethod
    def delete_candidate(candidate_id: int, soft_delete: bool = True) -> bool:
        """Удаляет кандидата"""
        logger.info(f"Facade: удаление кандидата {candidate_id}")
        return remove_candidate(candidate_id, soft_delete)
    
    @staticmethod
    def save_candidate(candidate_data: Dict[str, Any], file_path: str = None) -> int:
        """Сохраняет кандидата напрямую в БД"""
        logger.info(f"Facade: сохранение кандидата")
        return db_save_candidate(candidate_data, file_path)
    
    @staticmethod
    def search_candidates(
        skills: List[str] = None,
        min_experience: int = None,
        position: str = None,
        query_text: str = None,
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """ Поиск кандидатов по критериям  """
        logger.info(f"Facade: поиск кандидатов (skills={skills}, query_text={query_text})")
        return search_candidates_by_criteria(
            skills=skills or [],
            min_experience=min_experience,
            position=position,
            query_text=query_text,
            top_n=top_n
        )
    
    
    @staticmethod
    def add_job(
        title: str,
        level: str = "middle",
        skills: List[str] = None,
        experience: int = 0,
        description: str = ""
    ) -> int:
        """Добавляет новую вакансию"""
        logger.info(f"Facade: добавление вакансии {title}")
        return add_job(title, level, skills, experience, description)
    
    @staticmethod
    def get_job(job_id: int) -> Optional[Dict[str, Any]]:
        """Получает вакансию по ID"""
        logger.debug(f"Facade: получение вакансии {job_id}")
        return get_job_by_id(job_id)
    
    @staticmethod
    def get_all_jobs(active_only: bool = True) -> List[Dict[str, Any]]:
        """Возвращает все вакансии из БД."""
        logger.debug(f"Facade: получение всех вакансий (active_only={active_only})")
        return get_all_jobs_list(active_only=active_only)

    @staticmethod
    def get_all_jobs_dict(active_only: bool = True) -> List[Dict[str, Any]]:
        """Псевдоним get_all_jobs — для обратной совместимости."""
        return HRAgentFacade.get_all_jobs(active_only=active_only)

    @staticmethod
    def get_archived_jobs() -> List[Dict[str, Any]]:
        """Возвращает архивные вакансии."""
        return get_all_jobs_with_status("archived")
    
    @staticmethod
    def update_job(job_id: int, **fields) -> bool:
        """Обновляет вакансию"""
        logger.info(f"Facade: обновление вакансии {job_id}")
        return update_job_info(job_id, **fields)
    
    @staticmethod
    def delete_job(job_id: int) -> bool:
        """Удаляет вакансию"""
        logger.info(f"Facade: удаление вакансии {job_id}")
        return remove_job(job_id)
    
    @staticmethod
    def delete_job_from_db(job_id: int) -> bool:
        """Удаляет вакансию напрямую из БД"""
        logger.info(f"Facade: удаление вакансии из БД {job_id}")
        return delete_job(job_id)
    
    @staticmethod
    def archive_job(job_id: int) -> bool:
        """Архивирует вакансию"""
        logger.info(f"Facade: архивация вакансии {job_id}")
        return archive_job_by_id(job_id)
    
    @staticmethod
    def activate_job(job_id: int) -> bool:
        """Активирует архивную вакансию"""
        logger.info(f"Facade: активация вакансии {job_id}")
        return activate_job_by_id(job_id)
    
    @staticmethod
    def search_jobs(
        skills: List[str] = None,
        level: str = None,
        min_experience: int = None
    ) -> List[Dict[str, Any]]:
        """Ищет вакансии по критериям"""
        logger.debug(f"Facade: поиск вакансий (skills={skills}, level={level})")
        return search_jobs_by_criteria(skills=skills, level=level, min_experience=min_experience)
    
    @staticmethod
    def get_jobs_statistics() -> Dict[str, Any]:
        """Возвращает статистику по вакансиям"""
        logger.debug("Facade: получение статистики вакансий")
        return get_jobs_statistics()
    
    
    @staticmethod
    def match_candidates(job_id: int, top_n: int = 5) -> Dict[str, Any]:
        """ Подбирает кандидатов для вакансии """
        logger.info(f"Facade: matching для вакансии {job_id}")
        
        job = get_job_by_id(job_id)
        
        if not job:
            return {"error": f"Вакансия с ID {job_id} не найдена"}
        
        scored_candidates = match_candidates_to_job(job, None, 0.5, 0.3, 0.2)
        
        for c in scored_candidates:
            c["match_percent"] = c.get("total_score", 0)
        
        return {
            "job": job,
            "top_candidates": scored_candidates[:top_n],
            "total_candidates": len(scored_candidates)
        }
    
    @staticmethod
    def match_several_jobs(job_ids: List[int], top_n: int = 5) -> List[Dict[str, Any]]:
        """Подбирает кандидатов для нескольких вакансий"""
        logger.info(f"Facade: matching для вакансий {job_ids}")
        return match_by_job_ids(job_ids, top_n)
    
    
    @staticmethod
    def generate_test(
        direction: str,
        level: str,
        tech_stack: List[str] = None,
        candidate_name: str = None
    ) -> Dict[str, Any]:
        """Генерирует тестовое задание"""
        logger.info(f"Facade: генерация теста {direction}/{level}")
        return generate_test_task(direction, level, tech_stack, candidate_name)
    
    @staticmethod
    def generate_onboarding(
        candidate_name: str,
        candidate_email: str = None,
        department: str = "development",
        level: str = None,
        start_date: str = None
    ) -> Dict[str, Any]:
        """Генерирует план онбординга"""
        logger.info(f"Facade: генерация онбординга для {candidate_name}")
        return create_onboarding_plan(candidate_name, candidate_email, department, level, start_date)
    
    
    @staticmethod
    def create_survey(title: str, survey_type: str, department: str = None) -> int:
        """Создаёт опрос (NPS или Pulse)"""
        logger.info(f"Facade: создание опроса '{title}' типа {survey_type}")
        return db_create_survey(title, survey_type, department)
    
    @staticmethod
    def analyze_survey(survey_id: int) -> Dict[str, Any]:
        """Анализирует результаты опроса"""
        logger.info(f"Facade: анализ опроса {survey_id}")
        return analyze_survey_results(survey_id)
    
    @staticmethod
    def get_all_surveys(active_only: bool = True) -> List[Dict[str, Any]]:
        """Возвращает список всех опросов"""
        logger.debug(f"Facade: получение списка опросов (active_only={active_only})")
        return get_all_surveys(active_only)
    
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Получает общую статистику"""
        logger.debug("Facade: получение статистики")
        return get_overall_statistics()
    
    @staticmethod
    def get_quick_stats() -> Dict[str, Any]:
        """Получает быструю статистику"""
        logger.debug("Facade: получение быстрой статистики")
        return get_quick_stats()
    
    @staticmethod
    def export_candidates(file_path: str) -> bool:
        """Экспортирует кандидатов в JSON"""
        logger.info(f"Facade: экспорт кандидатов в {file_path}")
        return export_candidates_to_json(file_path)
    
    @staticmethod
    def export_jobs(file_path: str) -> bool:
        """Экспортирует вакансии в JSON"""
        logger.info(f"Facade: экспорт вакансий в {file_path}")
        return export_jobs_to_json(file_path)
    
    
    @staticmethod
    def format_candidate(candidate: Dict[str, Any]) -> str:
        """Форматирует кандидата для вывода"""
        return format_candidate_for_display(candidate)
    
    @staticmethod
    def format_candidates(candidates: List[Dict[str, Any]], limit: int = 20) -> str:
        """Форматирует список кандидатов"""
        return format_candidates_list(candidates, limit)
    
    @staticmethod
    def format_job(job: Dict[str, Any]) -> str:
        """Форматирует вакансию для вывода"""
        return format_job_for_display(job)
    
    @staticmethod
    def format_jobs(jobs: List[Dict[str, Any]], limit: int = 15) -> str:
        """Форматирует список вакансий"""
        return format_jobs_list(jobs, limit)
    
    @staticmethod
    def format_search_results(results: List[Dict[str, Any]], limit: int = 10) -> str:
        """Форматирует результаты поиска"""
        return format_search_results(results, limit)
    
    
    @staticmethod
    def create_nps_chart(survey_id: int) -> Optional[str]:
        """Создаёт график NPS опроса"""
        make_chart = make_nps_chart
        
        results = analyze_survey_results(survey_id)
        if "error" in results:
            return None
        
        return make_chart(
            promoters=results.get('promoters', 0),
            passives=results.get('passives', 0),
            detractors=results.get('detractors', 0),
            survey_title=results.get('survey_title', f"Опрос #{survey_id}")
        )
    
    @staticmethod
    def create_pulse_chart(survey_id: int) -> Optional[str]:
        """Создаёт график динамики Pulse опроса"""
        make_chart = make_pulse_chart
        
        survey = get_survey(survey_id)
        if not survey or survey.get('type') != 'pulse':
            return None
        
        responses = get_responses(survey_id)
        if not responses:
            return None
        
        responses_sorted = sorted(responses, key=lambda x: x.get('created_at', ''))
        
        satisfaction_scores = []
        energy_scores = []
        dates = []
        
        for r in responses_sorted:
            answers = r.get('answers', {})
            if 'satisfaction' in answers:
                satisfaction_scores.append(float(answers['satisfaction']))
            if 'energy' in answers:
                energy_scores.append(float(answers['energy']))
            created = r.get('created_at', '')
            if created:
                dates.append(created[:10])  # YYYY-MM-DD
        
        if not satisfaction_scores:
            return None
        
        return make_chart(
            satisfaction_scores=satisfaction_scores,
            energy_scores=energy_scores[:len(satisfaction_scores)],
            dates=dates[:len(satisfaction_scores)],
            survey_title=survey.get('title', f"Опрос #{survey_id}")
        )
    
    
    @staticmethod
    def get_department_by_role(role: str) -> str:
        """Определяет отдел по названию должности"""
        department_map = {
            "разработчик": "development", "программист": "development", "developer": "development",
            "devops": "development", "backend": "development", "frontend": "development",
            "fullstack": "development", "engineer": "development", "qa": "development",
            "тестировщик": "development", "mobile": "development", "ios": "development", "android": "development",
            "аналитик": "analytics", "analyst": "analytics", "data analyst": "analytics",
            "бизнес-аналитик": "analytics", "системный аналитик": "analytics",
            "менеджер": "management", "manager": "management", "руководитель": "management",
            "тимлид": "management", "team lead": "management", "project manager": "management",
            "product manager": "management", "pm": "management", "product owner": "management",
            "маркетолог": "marketing", "marketing": "marketing", "smm": "marketing",
            "продавец": "sales", "sales": "sales", "менеджер по продажам": "sales",
            "hr": "hr", "рекрутер": "hr", "recruiter": "hr",
            "бухгалтер": "finance", "финансист": "finance", "accountant": "finance",
            "юрист": "legal", "legal": "legal",
            "дизайнер": "design", "designer": "design", "ui": "design", "ux": "design"
        }
        
        role_lower = role.lower()
        for key, value in department_map.items():
            if key in role_lower:
                return value
        
        return "development"
    
    @staticmethod
    def detect_level_by_role(role: str) -> str:
        """Определяет уровень по названию должности"""
        role_lower = role.lower()
        
        if "junior" in role_lower or "джуниор" in role_lower or "стажёр" in role_lower:
            return "junior"
        elif "senior" in role_lower or "сеньор" in role_lower or "lead" in role_lower:
            return "senior"
        else:
            return "middle"
    
    @staticmethod
    def find_candidates_for_new_job(
        job_title: str,
        job_skills: List[str],
        job_experience: int,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """Находит кандидатов для новой вакансии"""
        logger.info(f"Facade: поиск кандидатов для новой вакансии: {job_title}")
        
        db_search = db_search_candidates
        
        candidates = db_search(
            query_skills=job_skills,
            min_experience=job_experience,
            position=job_title,
            min_match_percent=0
        )
        
        logger.info(f"✅ Найдено кандидатов: {len(candidates)}")
        
        return {
            "job": {
                "title": job_title,
                "skills": job_skills,
                "experience": job_experience
            },
            "candidates": candidates[:top_n],
            "total_found": len(candidates)
        }
    
    @staticmethod
    def get_full_candidate_info(candidate_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает полную информацию о кандидате с форматированием"""
        logger.debug(f"Facade: получение полной информации о кандидате ID: {candidate_id}")
        candidate = get_candidate(candidate_id)
        if not candidate:
            logger.warning(f"Кандидат с ID {candidate_id} не найден")
            return None
        
        return {
            "data": candidate,
            "formatted": format_candidate_for_display(candidate)
        }


    @staticmethod
    def get_candidate_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
        """Находит кандидата по Telegram ID."""
        return get_candidate_by_telegram_id(telegram_id)

    @staticmethod
    def update_candidate_status(candidate_id: int, status: str = None, **kwargs) -> bool:
        """Обновляет статус кандидата и дополнительные поля."""
        return update_candidate_status(candidate_id, status, **kwargs)

    @staticmethod
    def archive_candidate(candidate_id: int, reason: str = None) -> bool:
        """Архивирует кандидата с указанием причины."""
        return db_archive_candidate(candidate_id, reason)

    @staticmethod
    def restore_from_archive(candidate_id: int) -> bool:
        """Восстанавливает кандидата из архива."""
        return db_restore_from_archive(candidate_id)

    @staticmethod
    def get_archived_candidates(limit: int = 100) -> List[Dict[str, Any]]:
        """Возвращает список архивированных кандидатов."""
        return db_get_archived_candidates(limit)

    @staticmethod
    def is_candidate_archived(candidate_id: int) -> bool:
        """Проверяет, находится ли кандидат в архиве."""
        return db_is_candidate_archived(candidate_id)

    @staticmethod
    def delete_archived_candidate(candidate_id: int) -> bool:
        """Навсегда удаляет кандидата из архива."""
        return db_delete_archived_candidate(candidate_id)

    @staticmethod
    def delete_all_archived_candidates() -> int:
        """Навсегда удаляет всех кандидатов из архива."""
        return db_delete_all_archived_candidates()

    @staticmethod
    def is_candidate_in_notification_queue(candidate_id: int, hours: int = 24) -> bool:
        """Проверяет, есть ли кандидат в очереди уведомлений."""
        return is_candidate_already_in_queue(candidate_id, hours)

    @staticmethod
    def add_to_notification_queue(candidate_id: int, name: str, position: str = "") -> None:
        """Добавляет кандидата в очередь уведомлений."""
        db_add_to_notification_queue(candidate_id, name, position)


    @staticmethod
    def save_onboarding_progress(candidate_id: int, step: int, completed_tasks: list) -> bool:
        """Сохраняет прогресс онбординга кандидата."""
        return db_save_onboarding_progress(candidate_id, step, completed_tasks)

    @staticmethod
    def get_onboarding_progress(candidate_id: int) -> Dict[str, Any]:
        """Возвращает прогресс онбординга кандидата."""
        return db_get_onboarding_progress(candidate_id)

    @staticmethod
    def start_onboarding(candidate_id: int) -> bool:
        """Запускает онбординг для кандидата."""
        return db_start_onboarding(candidate_id)

    @staticmethod
    def complete_onboarding(candidate_id: int) -> bool:
        """Отмечает онбординг как завершённый."""
        return db_complete_onboarding(candidate_id)


    @staticmethod
    def create_job(job_data: Dict[str, Any]) -> int:
        """Создаёт новую вакансию. Возвращает ID."""
        return db_create_job(**job_data)

    @staticmethod
    def update_job_fields(job_id: int, **fields) -> bool:
        """Обновляет поля вакансии."""
        return db_update_job(job_id, **fields)


    @staticmethod
    def submit_survey_response(
        survey_id: int,
        answers: Dict[str, Any],
        respondent_name: str = None,
        respondent_email: str = None,
        feedback: str = None,
    ) -> bool:
        """Сохраняет ответ на опрос от кандидата."""
        return db_submit_response(
            survey_id=survey_id,
            answers=answers,
            respondent_name=respondent_name,
            respondent_email=respondent_email,
            feedback=feedback,
        )

    @staticmethod
    def get_survey_response_count(survey_id: int) -> int:
        """Возвращает количество ответов на опрос."""
        return db_get_response_count(survey_id)

    @staticmethod
    def get_survey(survey_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает опрос по ID."""
        return get_survey(survey_id)


    @staticmethod
    def register_candidate(telegram_id: int, name: str = None) -> bool:
        """Регистрирует кандидата по Telegram ID."""
        try:
            existing = get_candidate_by_telegram_id(telegram_id)
            if not existing:
                candidate_data = {
                    "name": name or "Кандидат",
                    "telegram_id": telegram_id,
                    "source": "telegram",
                    "status": "new"
                }
                db_save_candidate(candidate_data, None)
                logger.info(f"✅ Зарегистрирован новый кандидат: {telegram_id} ({name or 'Кандидат'})")
            else:
                logger.info(f"✅ Кандидат {telegram_id} уже зарегистрирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации кандидата {telegram_id}: {e}")
            return False


    @staticmethod
    def add_interview_slot(hr_id: int, slot_date: str, slot_time: str):
        """Добавляет слот собеседования."""
        return db_add_slot(hr_id, slot_date, slot_time)

    @staticmethod
    def get_all_interview_slots(only_free: bool = True) -> List[Dict[str, Any]]:
        """Возвращает все слоты собеседований."""
        return db_get_all_slots(only_free)

    @staticmethod
    def get_interview_slots_by_hr(hr_id: int) -> List[Dict[str, Any]]:
        """Возвращает слоты конкретного HR."""
        return db_get_slots_by_hr(hr_id)

    @staticmethod
    def get_interview_slots_by_date(date: str, hr_id: int = None) -> List[Dict[str, Any]]:
        """Возвращает слоты на определённую дату."""
        return db_get_slots_by_date(date, hr_id)

    @staticmethod
    def book_interview_slot(slot_id: int, candidate_db_id: int):
        """Бронирует слот для кандидата."""
        return db_book_slot(slot_id, candidate_db_id)

    @staticmethod
    def cancel_interview_booking(slot_id: int, hr_id: int = None):
        """Отменяет бронирование слота (HR)."""
        return db_cancel_booking(slot_id, hr_id)

    @staticmethod
    def cancel_interview_by_candidate(slot_id: int, candidate_db_id: int):
        """Отменяет бронирование слота (кандидат)."""
        return db_cancel_booking_by_candidate(slot_id, candidate_db_id)

    @staticmethod
    def get_candidate_interview_slot(candidate_db_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает слот кандидата."""
        return db_get_candidate_slot(candidate_db_id)

    @staticmethod
    def get_interview_slot_by_id(slot_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает слот по ID."""
        return db_get_slot_by_id(slot_id)

    @staticmethod
    def delete_interview_slot(slot_id: int, hr_id: int):
        """Удаляет слот."""
        return db_delete_slot(slot_id, hr_id)

    @staticmethod
    def delete_free_slots_by_date(date: str, hr_id: int):
        """Удаляет все свободные слоты на дату."""
        return db_delete_free_slots_by_date(date, hr_id)

    @staticmethod
    def generate_interview_slots_for_date(
        hr_id: int, date: str,
        start_time: str = "09:00", end_time: str = "18:00",
        interval_minutes: int = 60,
    ):
        """Генерирует слоты на весь рабочий день."""
        return db_generate_slots_for_date(hr_id, date, start_time, end_time, interval_minutes)

    @staticmethod
    def get_free_slots_grouped_by_date(limit_days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """Возвращает свободные слоты, сгруппированные по датам."""
        return db_get_free_slots_grouped_by_date(limit_days)

    @staticmethod
    def get_interview_settings() -> Dict[str, Any]:
        """Возвращает настройки собеседований."""
        return db_get_interview_settings()

    @staticmethod
    def is_date_fully_booked(date: str, hr_id: int) -> bool:
        """Проверяет, все ли слоты на дату заняты."""
        return db_is_date_fully_booked(date, hr_id)

    @staticmethod
    def has_free_slots(date: str, hr_id: int) -> bool:
        """Проверяет, есть ли свободные слоты на дату."""
        return db_has_free_slots(date, hr_id)

    @staticmethod
    def delete_survey(survey_id: int) -> bool:
        """Удаляет опрос и все ответы на него."""
        return db_delete_survey(survey_id)

    @staticmethod
    def delete_all_surveys() -> bool:
        """Удаляет все опросы и все ответы."""
        return db_delete_all_surveys()

    @staticmethod
    def get_all_candidates_full() -> list:
        """Возвращает всех кандидатов с полными данными."""
        return db_get_all_candidates_full()

    @staticmethod
    def get_resume_from_db(candidate_id: int):
        """Возвращает файл резюме из БД (bytes, content_type)."""
        return db_get_resume_from_db(candidate_id)

    @staticmethod
    def has_resume_in_db(candidate_id: int) -> bool:
        """Проверяет, есть ли файл резюме в БД."""
        return db_has_resume_in_db(candidate_id)
