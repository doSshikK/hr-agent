#!/usr/bin/env python3
"""
Тесты для utils/formatters.py
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.formatters import (
    format_skills,
    format_list_preview,
    format_candidate_for_display,
    format_candidates_list,
    format_job_for_display,
    format_jobs_list,
    format_search_results,
    format_parsed_resume,
    format_overall_statistics,
    format_match_results_universal,
)


class TestFormatSkills:
    """Тесты для format_skills"""

    def test_format_skills_normal(self):
        skills = ["Python", "Django", "PostgreSQL"]
        result = format_skills(skills, limit=2)
        assert "Python" in result
        assert "Django" in result
        assert "+1" in result

    def test_format_skills_empty(self):
        result = format_skills([])
        assert result == "—"

    def test_format_skills_no_limit(self):
        skills = ["Python", "Django"]
        result = format_skills(skills, limit=5)
        assert result == "Python, Django"


class TestFormatListPreview:
    """Тесты для format_list_preview"""

    def test_format_list_preview_normal(self):
        items = ["a", "b", "c", "d"]
        result = format_list_preview(items, limit=2)
        assert "a, b" in result
        assert "+2" in result

    def test_format_list_preview_empty(self):
        result = format_list_preview([])
        assert result == "—"


class TestFormatCandidateForDisplay:
    """Тесты для format_candidate_for_display"""

    def test_format_candidate_minimal(self):
        candidate = {"name": "Иван Иванов", "experience_years": 5}
        result = format_candidate_for_display(candidate)
        assert "Иван Иванов" in result
        assert "5 лет" in result

    def test_format_candidate_full(self):
        candidate = {
            "name": "Петр Петров",
            "email": "petr@test.com",
            "phone": "+79001234567",
            "experience_years": 3,
            "last_position": "Python Developer",
            "last_company": "Яндекс",
            "skills": ["Python", "Django", "PostgreSQL"],
            "match_percent": 85,
        }
        result = format_candidate_for_display(candidate)
        assert "petr@test.com" in result
        assert "85%" in result


class TestFormatCandidatesList:
    """Тесты для format_candidates_list"""

    def test_format_candidates_list_empty(self):
        result = format_candidates_list([])
        assert "не найдено" in result

    def test_format_candidates_list_with_data(self):
        candidates = [
            {"id": 1, "name": "Иван", "experience_years": 5, "skills": ["Python"]},
            {"id": 2, "name": "Петр", "experience_years": 3, "skills": ["Java"]},
        ]
        result = format_candidates_list(candidates, limit=2)
        assert "Иван" in result
        assert "Петр" in result
        assert "5 лет" in result


class TestFormatJobForDisplay:
    """Тесты для format_job_for_display"""

    def test_format_job_minimal(self):
        job = {"title": "Python Developer", "level": "middle", "experience": 3}
        result = format_job_for_display(job)
        assert "Python Developer" in result
        assert "middle" in result

    def test_format_job_with_skills(self):
        job = {
            "title": "Senior Python Dev",
            "level": "senior",
            "experience": 5,
            "skills": ["Python", "Django", "PostgreSQL"],
            "description": "Разработка backend сервисов",
            "status": "active",
        }
        result = format_job_for_display(job)
        assert "Senior" in result
        assert "актив" in result.lower() or "active" in result.lower()


class TestFormatJobsList:
    """Тесты для format_jobs_list"""

    def test_format_jobs_list_empty(self):
        result = format_jobs_list([])
        assert "не найдено" in result

    def test_format_jobs_list_with_data(self):
        jobs = [
            {"id": 1, "title": "Python Dev", "level": "middle", "experience": 3},
            {"id": 2, "title": "Java Dev", "level": "senior", "experience": 5},
        ]
        result = format_jobs_list(jobs, limit=2)
        assert "Python Dev" in result
        assert "Java Dev" in result


class TestFormatSearchResults:
    """Тесты для format_search_results"""

    def test_format_search_results_empty(self):
        result = format_search_results([])
        assert "не найдены" in result

    def test_format_search_results_with_data(self):
        results = [
            {"name": "Иван", "match_percent": 85, "experience_years": 5, "skills": ["Python"]},
            {"name": "Петр", "match_percent": 45, "experience_years": 3, "skills": ["Java"]},
        ]
        result = format_search_results(results, limit=2)
        assert "Иван" in result
        assert "85%" in result


class TestFormatParsedResume:
    """Тесты для format_parsed_resume"""

    def test_format_parsed_resume_error(self):
        result = format_parsed_resume({"error": "Файл не найден"})
        assert "ошибка" in result.lower()

    def test_format_parsed_resume_success(self):
        parsed = {
            "name": "Иван Иванов",
            "email": "ivan@test.com",
            "phone": "+79001234567",
            "experience_years": 5,
            "last_position": "Python Developer",
            "skills": ["Python", "Django", "PostgreSQL"],
        }
        result = format_parsed_resume(parsed)
        assert "Иван Иванов" in result
        assert "5 лет" in result


class TestFormatOverallStatistics:
    """Тесты для format_overall_statistics"""

    def test_format_statistics(self):
        stats = {
            "summary": {
                "total_candidates": 10,
                "total_jobs": 5,
                "total_surveys": 3,
                "total_responses": 15,
            },
            "candidates": {"avg_experience": 4.5, "unique_skills": 20},
            "jobs": {"active": 3, "avg_experience_required": 3.5},
            "surveys": {"avg_nps_score": 45},
        }
        result = format_overall_statistics(stats)
        assert "10" in result
        assert "5" in result


class TestFormatMatchResultsUniversal:
    """Тесты для format_match_results_universal"""

    def test_format_match_results_empty(self):
        result = format_match_results_universal("Python Dev", [])
        assert "не найдено" in result

    def test_format_match_results_with_candidates(self):
        candidates = [
            {"name": "Иван", "match_percent": 85, "experience_years": 5, "skills": ["Python"]},
        ]
        result = format_match_results_universal("Python Dev", candidates)
        assert "Python Dev" in result
        assert "Иван" in result


if __name__ == "__main__":
    pytest.main(["-v"])
