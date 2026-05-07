#!/usr/bin/env python3
"""
Тесты для onboarding_generator.py
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.onboarding_generator import (
    generate_onboarding_plan,
    format_onboarding_plan,
    detect_level_by_keywords,
    ONBOARDING_TEMPLATES
)


class TestGenerateOnboarding:

    @pytest.mark.parametrize("department", ["development", "hr", "design"])
    def test_departments(self, department):
        """Проверяет генерацию для разных отделов"""
        plan = generate_onboarding_plan(candidate={"name": "Тест"}, department=department)
        
        assert plan["candidate_name"] == "Тест"
        assert len(plan["checklist"]) > 0
        assert len(plan["meetings"]) > 0

    @pytest.mark.parametrize("level", ["junior", "senior"])
    def test_development_levels(self, level):
        """Проверяет уровни для разработки"""
        plan = generate_onboarding_plan(
            candidate={"name": "Dev"},
            department="development",
            level=level
        )
        assert plan["level"] == level

    def test_middle_level_default(self):
        """Проверяет уровень по умолчанию"""
        plan = generate_onboarding_plan(candidate={"name": "Dev"}, department="development")
        assert plan["level"] == "middle"

    def test_non_dev_default_level(self):
        """Проверяет уровень для не-development отделов"""
        plan = generate_onboarding_plan(candidate={"name": "Analyst"}, department="analytics")
        assert plan["level"] == "default"


class TestDates:

    def test_with_specific_start_date(self):
        """Проверяет установку конкретной даты"""
        plan = generate_onboarding_plan(
            candidate={"name": "Test"},
            department="development",
            start_date="2026-05-15"
        )
        assert plan["start_date_readable"] == "15.05.2026"


class TestStructure:

    def test_checklist_has_tasks(self):
        """Проверяет структуру чек-листа"""
        plan = generate_onboarding_plan(candidate={"name": "Test"}, department="development")
        
        for task in plan["checklist"]:
            assert "task" in task
            assert len(task["task"]) > 0

    def test_meetings_have_required_fields(self):
        """Проверяет структуру встреч"""
        plan = generate_onboarding_plan(candidate={"name": "Test"}, department="development")
        
        for meeting in plan["meetings"]:
            assert "date_readable" in meeting
            assert "time" in meeting
            assert "with" in meeting


class TestLogic:

    @pytest.mark.parametrize("text,expected", [
        ("junior developer", "junior"),
        ("middle developer", "middle"),
        ("senior developer", "senior"),
    ])
    def test_detect_level(self, text, expected):
        """Проверяет определение уровня"""
        assert detect_level_by_keywords(text) == expected


class TestTemplates:

    def test_development_has_levels(self):
        """Проверяет наличие уровней в development"""
        dev = ONBOARDING_TEMPLATES["development"]
        for level in ["junior", "middle", "senior"]:
            assert level in dev["levels"]


if __name__ == "__main__":
    pytest.main(["-v"])
