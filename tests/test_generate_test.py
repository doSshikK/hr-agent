#!/usr/bin/env python3
"""
Тесты для модуля test_generator.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.test_generator import generate_test, format_test


class TestGenerateTest:

    @pytest.mark.parametrize("direction,level", [
        ("frontend", "junior"),
        ("backend", "senior"),
    ])
    def test_generate_valid_combinations(self, direction, level):
        """Проверяет генерацию для валидных комбинаций"""
        test = generate_test(direction=direction, level=level, use_llm=False)
        
        assert "error" not in test
        assert test["direction"] == direction
        assert test["level"] == level

    def test_generate_with_tech_stack(self):
        """Проверяет генерацию с указанием стека"""
        test = generate_test(
            direction="fullstack",
            level="middle",
            tech_stack=["Python", "FastAPI"],
            use_llm=False
        )
        assert test["stack"] == ["Python", "FastAPI"]

    def test_generate_with_candidate_name(self):
        """Проверяет персонализацию теста"""
        name = "Иван Иванов"
        test = generate_test(direction="frontend", level="middle", candidate_name=name, use_llm=False)
        assert name in test.get("title", "")

    def test_invalid_direction(self):
        """Проверяет обработку невалидного направления"""
        test = generate_test(direction="invalid", level="middle", use_llm=False)
        assert "error" in test

    def test_invalid_level(self):
        """Проверяет обработку невалидного уровня"""
        test = generate_test(direction="frontend", level="invalid", use_llm=False)
        assert "error" in test


class TestStructure:

    def test_required_fields_exist(self):
        """Проверяет наличие обязательных полей"""
        test = generate_test(direction="backend", level="middle", use_llm=False)
        
        required = ["title", "direction", "level", "tasks", "requirements", "deadline"]
        for field in required:
            assert field in test

    def test_fields_not_empty(self):
        """Проверяет что задачи и требования не пустые"""
        test = generate_test(direction="frontend", level="middle", use_llm=False)
        
        assert len(test["tasks"]) > 0
        assert len(test["requirements"]) > 0


class TestFormatting:

    def test_format_success(self):
        """Проверяет форматирование"""
        test = generate_test(direction="frontend", level="middle", use_llm=False)
        formatted = format_test(test)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 50

    def test_format_error(self):
        """Проверяет форматирование ошибки"""
        formatted = format_test({"error": "Ошибка"})
        assert "❌" in formatted

class TestGenerateTestFallback:
    """Тесты fallback-генерации (без LLM)"""
    
    def test_all_directions_fallback(self):
        """Проверяет все направления"""
        directions = ["production", "construction", "logistics", "office",
                      "sales", "marketing", "finance", "hr"]
        for direction in directions:
            test = generate_test(direction=direction, level="middle", use_llm=False)
            assert "error" not in test
            assert test["direction"] == direction

    def test_universal_fallback_requirements(self):
        """Проверяет универсальные требования"""
        test = generate_test(direction="production", level="junior", use_llm=False)
        requirements = test.get("requirements", [])
        assert len(requirements) > 0
        assert any("безопасн" in r.lower() for r in requirements)

    def test_tech_stack_includes_in_fallback(self):
        """Проверяет, что tech_stack попадает в требования"""
        tech = ["AutoCAD", "SolidWorks"]
        test = generate_test(direction="construction", level="middle",
                             tech_stack=tech, use_llm=False)
        requirements_str = " ".join(test.get("requirements", []))
        assert "AutoCAD" in requirements_str or "SolidWorks" in requirements_str

if __name__ == "__main__":
    pytest.main(["-v"])
