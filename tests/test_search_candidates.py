#!/usr/bin/env python3
"""
Тесты поиска кандидатов и matching
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.job_matcher import (
    normalize_skill,
    normalize_skills_set,
    calculate_skills_match,
    calculate_experience_match,
    calculate_score
)


class TestNormalization:

    @pytest.mark.parametrize("input_skill,expected", [
        ("Python", "python"),
        (" PYTHON ", "python"),
        ("py", "python"),
        ("js", "javascript"),
    ])
    def test_normalize_skill(self, input_skill, expected):
        """Проверяет нормализацию навыков"""
        assert normalize_skill(input_skill) == expected

    def test_normalize_skills_set(self):
        """Проверяет нормализацию множества"""
        skills = ["Python", "py", "JS", "javascript"]
        result = normalize_skills_set(skills)
        assert result == {"python", "javascript"}


class TestScoring:

    @pytest.mark.parametrize("job_skills,candidate_skills,expected_match", [
        ({"python", "django"}, {"python", "django"}, 1.0),
        ({"python", "django"}, {"python"}, 0.5),
        (set(), {"python"}, 0.5),
    ])
    def test_skills_match(self, job_skills, candidate_skills, expected_match):
        """Проверяет расчёт совпадения навыков"""
        match, matched, confidence, level = calculate_skills_match(job_skills, candidate_skills)
        assert match == expected_match
        assert confidence >= 0

    @pytest.mark.parametrize("candidate_exp,required_exp,expected", [
        (5, 3, 1.0),
        (3, 3, 1.0),
        (2, 3, 2/3),
        (0, 3, 0.0),
        (5, 0, 1.0),
    ])
    def test_experience_match(self, candidate_exp, required_exp, expected):
        """Проверяет расчёт совпадения по опыту"""
        result = calculate_experience_match(candidate_exp, required_exp)
        assert result == expected

    @pytest.mark.parametrize("skills_match,exp_match,edu_match,expected", [
        (1.0, 1.0, 1.0, 100),
        (0.5, 0.5, 0.5, 50),
        (0.2, 0.2, 0.2, 20),
    ])
    def test_calculate_total_score(self, skills_match, exp_match, edu_match, expected):
        """Проверяет расчёт итогового score"""
        score = calculate_score(skills_match, exp_match, edu_match, 0.5, 0.3, 0.2)
        assert score == expected

    def test_score_respects_weights(self):
        """Проверяет учёт весов"""
        score_high_skills = calculate_score(1.0, 0.0, 0.0, 0.7, 0.15, 0.15)
        score_low_skills = calculate_score(0.0, 1.0, 1.0, 0.7, 0.15, 0.15)
        assert score_high_skills > score_low_skills


if __name__ == "__main__":
    pytest.main(["-v"])
