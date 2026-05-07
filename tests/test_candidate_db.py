#!/usr/bin/env python3
"""
Тесты для candidate_db.py

Используют unittest.mock для изоляции от реальной PostgreSQL:
- нормализация навыков и скоринг работают без БД
- CRUD-тесты мокируют get_connection()
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNormalization:

    def test_normalize_skill(self):
        """Проверяет нормализацию навыков"""
        from app.db.candidate_db import normalize_skill

        assert normalize_skill("Python") == "python"
        assert normalize_skill(" PYTHON ") == "python"
        assert normalize_skill("js") == "javascript"
        assert normalize_skill("") == ""

    def test_normalize_skills_list(self):
        """Проверяет нормализацию списка навыков"""
        from app.db.candidate_db import normalize_skills_list

        result = normalize_skills_list(["Python", "JS", "java"])
        assert result == ["python", "javascript", "java"]


class TestScoring:

    def test_experience_score(self):
        """Проверяет расчёт оценки опыта"""
        from app.db.candidate_db import experience_score

        assert experience_score(5, 3) >= 1.0
        assert experience_score(2, 3) < 1.0
        assert experience_score(0, 3) == 0.0

    def test_position_score_basic(self):
        """Проверяет расчёт оценки должности"""
        from app.db.candidate_db import position_score

        assert position_score("backend", "backend") == 1.0
        assert position_score("backend developer", "backend") == 0.95
        result = position_score("java dev", "python dev")


def _make_mock_conn(fetchone=None, fetchall=None):
    """Фабрика: создаёт мок-соединение с PostgreSQL."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone
    mock_cursor.fetchall.return_value = fetchall or []

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestCRUDMocked:

    def test_get_candidate_returns_none_when_missing(self):
        """get_candidate возвращает None если записи нет."""
        from app.db.candidate_db import get_candidate

        mock_conn, mock_cursor = _make_mock_conn(fetchone=None)
        with patch("app.db.candidate_db.get_connection", return_value=mock_conn):
            result = get_candidate(9999)
        assert result is None

if __name__ == "__main__":
    pytest.main(["-v"])
