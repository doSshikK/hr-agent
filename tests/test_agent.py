#!/usr/bin/env python3
"""
Тесты для hr_agent.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.hr_agent import HRAgent, execute_tool
from app.agent.tools import TOOLS


@pytest.fixture
def mock_llm_client():
    with patch('app.agent.hr_agent.get_llm_client') as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def agent(mock_llm_client):
    agent = HRAgent()
    agent.client = mock_llm_client
    return agent


class TestAgentBasics:

    def test_init(self, agent):
        """Проверяет инициализацию агента"""
        assert agent.model
        assert "HR-агент" in agent.system_prompt

    def test_tools_structure(self):
        """Проверяет структуру TOOLS"""
        for tool in TOOLS:
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_key_tools_exist(self):
        """Проверяет наличие ключевых инструментов"""
        names = [t["function"]["name"] for t in TOOLS]
        for required in ["parse_resume", "search_candidates", "generate_test_task", "prepare_interview_invite"]:
            assert required in names


class TestExecuteTool:

    def test_unknown_tool(self):
        """Проверяет обработку неизвестного инструмента"""
        result = execute_tool("unknown_tool_name", {})
        assert "неизвестный" in result.lower()

    def test_parse_resume_missing_file(self):
        """Проверяет парсинг с несуществующим файлом"""
        result = execute_tool("parse_resume", {"file_path": "/nonexistent/file.pdf"})
        assert "ошибка" in result.lower() or "не найден" in result.lower()

    def test_match_candidates_no_job_id(self):
        """Проверяет matching без указания job_id"""
        result = execute_tool("match_candidates_to_job", {})
        assert "не указан" in result.lower()

    def test_prepare_interview_invite_requires_confirmation(self):
        """Tool готовит приглашение, но не отправляет его сразу."""
        session_data = {}
        candidate = {
            "id": 52,
            "name": "Гусаров Дмитрий",
            "interview_stage": None,
        }

        with patch("app.agent.hr_agent.HRAgentFacade.get_candidate", return_value=candidate):
            result = execute_tool(
                "prepare_interview_invite",
                {"candidate_id": 52, "position": "инженер-конструктор"},
                session_data,
            )

        assert "подтвердите" in result.lower()
        assert session_data["pending_action"]["type"] == "invite_candidate_to_interview"
        assert session_data["pending_action"]["candidate_id"] == 52

    def test_prepare_interview_invite_uses_last_candidate_for_pronoun(self):
        """Tool понимает 'его' через последнего найденного кандидата."""
        session_data = {"last_candidate": {"id": 52, "name": "Гусаров Дмитрий"}}
        candidate = {
            "id": 52,
            "name": "Гусаров Дмитрий",
            "interview_stage": None,
        }

        with patch("app.agent.hr_agent.HRAgentFacade.get_candidate", return_value=candidate):
            result = execute_tool(
                "prepare_interview_invite",
                {"candidate_name": "его"},
                session_data,
            )

        assert "подготовлено приглашение" in result.lower()
        assert session_data["pending_action"]["candidate_id"] == 52


class TestChat:

    def test_simple_response(self, agent, mock_llm_client):
        """Проверяет простой ответ без вызова инструментов"""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Привет! Я HR-агент", tool_calls=None))]
        mock_llm_client.chat.completions.create.return_value = mock_response

        result = agent.chat("Привет")
        assert "HR-агент" in result

    def test_error_handling(self, agent, mock_llm_client):
        """Проверяет обработку ошибок LLM"""
        mock_llm_client.chat.completions.create.side_effect = Exception("API Error")
        result = agent.chat("test")
        assert "ошибка" in result.lower() or "недоступен" in result.lower()


if __name__ == "__main__":
    pytest.main(["-v"])
