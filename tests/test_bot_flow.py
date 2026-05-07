#!/usr/bin/env python3
"""
Тесты для bot-слоя (упрощённые, без реального Telegram API)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.bot.utils import (
    extract_test_params,
    detect_direction_from_role,
    extract_name_from_text,
    format_years,
    validate_date,
)
from app.bot.keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_candidate_keyboard,
    get_vacancies_keyboard,
)
from app.bot.states import (
    CANCEL_WORDS,
    CANDIDATE_ADD_WORDS,
    TEST_TRIGGERS,
    ONBOARDING_TRIGGERS,
)


class TestUtils:
    """Тесты для bot/utils.py"""

    def test_extract_test_params_backend(self):
        result = extract_test_params("backend разработчик")
        assert result["direction"] == "backend"

    def test_extract_test_params_level(self):
        result = extract_test_params("junior python developer")
        assert result["level"] == "junior"

    def test_detect_direction_from_role(self):
        assert detect_direction_from_role("инженер") == "production"
        assert detect_direction_from_role("продавец") == "sales"
        assert detect_direction_from_role("бухгалтер") == "finance"

    def test_extract_name_from_text(self):
        assert extract_name_from_text("Иван Иванов") == "Иван Иванов"
        assert extract_name_from_text("отмена") is None

    def test_format_years(self):
        assert format_years(1) == "1 год"
        assert format_years(2) == "2 года"
        assert format_years(5) == "5 лет"

    def test_validate_date(self):
        is_valid, _, error = validate_date("15.05.2026")
        assert is_valid is True
        is_valid, _, error = validate_date("2026-05-15")
        assert is_valid is False


class TestKeyboards:
    """Тесты для bot/keyboards.py"""

    def test_get_main_keyboard(self):
        keyboard = get_main_keyboard()
        assert keyboard is not None
        buttons = [row[0].text for row in keyboard.keyboard if row]
        assert any("Вакансии" in b for b in buttons)

    def test_get_cancel_keyboard(self):
        keyboard = get_cancel_keyboard()
        assert keyboard is not None
        assert keyboard.keyboard[0][0].text == "❌ Отмена"

    def test_get_candidate_keyboard(self):
        keyboard = get_candidate_keyboard()
        assert keyboard is not None
        buttons = [row[0].text for row in keyboard.keyboard if row]
        assert any("Смотреть вакансии" in b for b in buttons)

    def test_get_vacancies_keyboard_has_archive(self):
        keyboard = get_vacancies_keyboard()
        buttons = [button.text for row in keyboard.keyboard for button in row]
        assert "📦 Архив вакансий" in buttons


class TestStates:
    """Тесты для bot/states.py"""

    def test_cancel_words(self):
        assert "отмена" in CANCEL_WORDS
        assert "cancel" in CANCEL_WORDS

    def test_candidate_add_words(self):
        words = " ".join(CANDIDATE_ADD_WORDS).lower()
        assert "добавить кандидата" in words or "новый кандидат" in words

    def test_test_triggers(self):
        triggers = " ".join(TEST_TRIGGERS).lower()
        assert "тест" in triggers or "тестовое" in triggers

    def test_onboarding_triggers(self):
        triggers = " ".join(ONBOARDING_TRIGGERS).lower()
        assert "онбординг" in triggers


class TestMiddlewares:
    """Тесты для bot/middlewares.py (синхронные функции)"""

    def test_get_role_function(self):
        from app.bot.middlewares import get_role
        mock_context = MagicMock()
        mock_context.user_data = {"role": "hr"}
        assert get_role(mock_context) == "hr"

    def test_get_role_default(self):
        from app.bot.middlewares import get_role
        mock_context = MagicMock()
        mock_context.user_data = {}
        assert get_role(mock_context) == "candidate"

    def test_is_hr_function(self):
        from app.bot.middlewares import is_hr
        mock_context = MagicMock()
        mock_context.user_data = {"is_hr": True}
        assert is_hr(mock_context) is True

    def test_is_hr_default(self):
        from app.bot.middlewares import is_hr
        mock_context = MagicMock()
        mock_context.user_data = {}
        assert is_hr(mock_context) is False

    def test_get_user_id_function(self):
        from app.bot.middlewares import get_user_id
        mock_context = MagicMock()
        mock_context.user_data = {"user_id": 123}
        assert get_user_id(mock_context) == 123

    def test_get_user_id_default(self):
        from app.bot.middlewares import get_user_id
        mock_context = MagicMock()
        mock_context.user_data = {}
        assert get_user_id(mock_context) == 0


@pytest.mark.asyncio
async def test_role_middleware_hr():
    """Тест для RoleMiddleware.__call__ (асинхронный)"""
    from app.bot.middlewares import RoleMiddleware

    mock_update = MagicMock()
    mock_update.effective_user.id = 123
    mock_context = MagicMock()
    mock_context.user_data = {}
    mock_context.bot_data = {"hr_agent": MagicMock()}
    mock_next = AsyncMock()

    with patch("app.bot.middlewares.settings") as mock_settings:
        mock_settings.is_hr.return_value = True

        middleware = RoleMiddleware()
        await middleware(mock_update, mock_context, mock_next)

        assert mock_context.user_data["role"] == "hr"
        assert mock_context.user_data["is_hr"] is True
        mock_next.assert_called_once()


class TestCommandsAdditional:
    """Дополнительные тесты для bot/commands.py"""

    def test_cancel_command_import(self):
        """Проверяет, что функция cancel_command существует и вызываема"""
        from app.bot.commands import cancel_command
        assert callable(cancel_command)

    def test_start_command_import(self):
        """Проверяет, что функция start существует и вызываема"""
        from app.bot.commands import start
        assert callable(start)


class TestHandlersBasics:
    """Базовые тесты для bot/handlers.py"""

    def test_handle_message_import(self):
        """Проверяет, что функция handle_message существует"""
        from app.bot.handlers import handle_message
        assert callable(handle_message)

    def test_handle_document_import(self):
        """Проверяет, что функция handle_document существует"""
        from app.bot.handlers import handle_document
        assert callable(handle_document)

    def test_hr_agent_not_none(self):
        """Проверяет, что hr_agent создаётся (через бота)"""
        from app.agent.hr_agent import HRAgent
        agent = HRAgent()
        assert agent is not None
        assert hasattr(agent, 'chat')

    def test_extract_search_position_for_invite(self):
        from app.bot.handlers import _extract_search_position_for_invite

        position = _extract_search_position_for_invite(
            "найди кандидата инженера-конструктора и пригласи его на собеседование"
        )

        assert position == "инженер-конструктор"

    def test_invite_parser_ignores_pronoun(self):
        from app.bot.interview_flow import parse_invite_message

        parsed = parse_invite_message("найди кандидата инженера-конструктора и пригласи его на собеседование")

        assert parsed is None

    @pytest.mark.asyncio
    async def test_chat_with_hr_agent_uses_bot_data(self):
        from app.bot.handlers import _chat_with_hr_agent

        mock_agent = MagicMock()
        mock_agent.chat.return_value = "ok"

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.bot_data = {"hr_agent": mock_agent}

        result = await _chat_with_hr_agent(mock_context, "найди кандидата")

        assert result == "ok"
        assert mock_context.user_data["hr_agent"] is mock_agent
        mock_agent.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_hr_agent_passes_recent_history(self):
        from app.bot.handlers import _chat_with_hr_agent

        mock_agent = MagicMock()
        mock_agent.chat.return_value = "ok"

        mock_context = MagicMock()
        mock_context.user_data = {"user_id": 123}
        mock_context.bot_data = {"hr_agent": mock_agent}

        history = [{"role": "user", "content": "найди инженера"}]

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.get_recent_conversation_history.return_value = history

            result = await _chat_with_hr_agent(mock_context, "пригласи его")

        assert result == "ok"
        mock_agent.chat.assert_called_once_with(
            "пригласи его",
            history=history,
            session_data=mock_context.user_data,
        )
        assert mock_facade.save_conversation_message.call_count == 2

    def test_cleanup_temp_file_removes_existing_file(self):
        from app.bot.handlers import _cleanup_temp_file

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        assert Path(tmp_path).exists()
        _cleanup_temp_file(tmp_path)

        assert not Path(tmp_path).exists()


class TestHandlerScenarios:
    """Тесты для различных сценариев обработки сообщений"""

    @pytest.mark.asyncio
    async def test_cancel_message_handling(self):
        """Тест обработки сообщения 'отмена'"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "❌ Отмена"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {"user_state": {"state": "test"}, "temp_data": {}}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.register_candidate = MagicMock()
            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_back_to_menu_handling(self):
        """Тест обработки сообщения '◀️ Назад в главное меню'"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "◀️ Назад в главное меню"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {"user_state": {"state": "test"}, "temp_data": {}}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.register_candidate = MagicMock()
            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_show_vacancies_handling(self):
        """Тест обработки сообщения '📋 Смотреть вакансии'"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "📋 Смотреть вакансии"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.get_all_jobs.return_value = [
                {"title": "Python Dev", "level": "middle", "experience": 3, "skills": ["Python"]}
            ]
            mock_facade.register_candidate = MagicMock()

            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_show_vacancies_empty(self):
        """Тест обработки пустого списка вакансий"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "📋 Смотреть вакансии"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.get_all_jobs.return_value = []
            mock_facade.register_candidate = MagicMock()

            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_show_archived_jobs_button(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "📦 Архив вакансий"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_settings.is_hr.return_value = True
            mock_facade.get_archived_jobs.return_value = [
                {"id": 2, "title": "Backend Dev", "level": "middle", "experience": 3, "skills": ["Python"]}
            ]

            await handle_message(mock_update, mock_context)

        answer = mock_update.message.reply_text.call_args.args[0]
        assert "АРХИВ ВАКАНСИЙ" in answer
        assert "Backend Dev" in answer

    @pytest.mark.asyncio
    async def test_candidate_search_by_skills(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "найди кандидата с Python и SQL"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_settings.is_hr.return_value = True
            mock_facade.search_candidates.return_value = [
                {"name": "Иван", "match_percent": 90, "experience_years": 4, "skills": ["Python", "SQL"]}
            ]

            await handle_message(mock_update, mock_context)

        mock_facade.search_candidates.assert_called_once()
        kwargs = mock_facade.search_candidates.call_args.kwargs
        assert kwargs["skills"] == ["python", "sql"]
        assert kwargs["position"] is None

    @pytest.mark.asyncio
    async def test_candidate_match_by_job_command(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "найди кандидата для вакансии 2"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_settings.is_hr.return_value = True
            mock_facade.match_candidates.return_value = {
                "job": {"title": "Backend Dev"},
                "top_candidates": [
                    {"name": "Иван", "match_percent": 88, "experience_years": 4, "skills": ["Python"]}
                ],
            }

            await handle_message(mock_update, mock_context)

        mock_facade.match_candidates.assert_called_once_with(job_id=2, top_n=10)
        answer = mock_update.message.reply_text.call_args.args[0]
        assert "ТОП КАНДИДАТОВ" in answer

    @pytest.mark.asyncio
    async def test_invite_pronoun_uses_last_candidate_context(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "пригласи его"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {
            "last_candidate": {"id": 52, "name": "Гусаров Дмитрий", "last_position": "Инженер-конструктор"}
        }
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_settings.is_hr.return_value = True
            mock_facade.get_candidate.return_value = {
                "id": 52,
                "name": "Гусаров Дмитрий",
                "last_position": "Инженер-конструктор",
                "interview_stage": None,
            }

            await handle_message(mock_update, mock_context)

        assert mock_context.user_data["pending_action"]["type"] == "invite_candidate_to_interview"
        assert mock_context.user_data["pending_action"]["candidate_id"] == 52
        answer = mock_update.message.reply_text.call_args.args[0]
        assert "Подготовлено приглашение" in answer

    @pytest.mark.asyncio
    async def test_generate_test_for_this_job_uses_last_job_context(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "создай тест для этой вакансии"
        mock_update.message.reply_text = AsyncMock()

        status_msg = AsyncMock()
        mock_update.message.reply_text.side_effect = [status_msg, None]

        mock_context = MagicMock()
        mock_context.user_data = {
            "last_job": {
                "id": 2,
                "title": "Инженер-конструктор",
                "level": "middle",
                "skills": ["AutoCAD", "SolidWorks"],
            }
        }
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade, \
             patch("app.services.test_generator.generate_test") as mock_generate, \
             patch("app.services.test_generator.format_test", return_value="Тест готов"):
            mock_settings.is_hr.return_value = True
            mock_generate.return_value = {"title": "Тест"}

            await handle_message(mock_update, mock_context)

        mock_generate.assert_called_once_with(
            direction="custom",
            level="middle",
            tech_stack=["AutoCAD", "SolidWorks"],
            candidate_name="Инженер-конструктор",
        )
        assert mock_context.user_data["temp_data"]["last_test"] == {"title": "Тест"}


class TestArchiveHandlers:
    """Тесты для обработки архивов"""

    @pytest.mark.asyncio
    async def test_restore_from_archive_invalid_id(self):
        """Тест восстановления из архива с неверным ID"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "восстановить из архива abc"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.register_candidate = MagicMock()
            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_delete_archived_candidate_requires_confirmation(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "удалить кандидата 52 из архива"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_settings.is_hr.return_value = True
            mock_facade.is_candidate_archived.return_value = True
            mock_facade.get_archived_candidates.return_value = [{"id": 52, "name": "Гусаров Дмитрий"}]

            await handle_message(mock_update, mock_context)

        assert mock_context.user_data["user_state"]["state"] == "confirm_delete_archived_candidate"
        assert mock_context.user_data["user_state"]["candidate_id"] == 52
        mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_confirm_delete_all_archived_candidates(self):
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "ДА"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {
            "user_state": {"state": "confirm_delete_all_archived_candidates", "count": 2}
        }
        mock_context.bot_data = {}

        with patch("app.bot.handlers.settings") as mock_settings, \
             patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_settings.is_hr.return_value = True
            mock_facade.delete_all_archived_candidates.return_value = 2

            await handle_message(mock_update, mock_context)

        mock_facade.delete_all_archived_candidates.assert_called_once()
        assert mock_context.user_data["user_state"] == {}
        mock_update.message.reply_text.assert_called()


class TestExportHandlers:
    """Тесты для обработки экспорта PDF"""

    @pytest.mark.asyncio
    async def test_export_onboarding_no_data(self):
        """Тест экспорта онбординга без данных"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "экспорт онбординга в pdf"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {"temp_data": {}}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.register_candidate = MagicMock()
            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_export_test_no_data(self):
        """Тест экспорта теста без данных"""
        from app.bot.handlers import handle_message

        mock_update = MagicMock()
        mock_update.effective_user.id = 123
        mock_update.message.text = "экспорт теста в pdf"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()
        mock_context.user_data = {"temp_data": {}}

        with patch("app.bot.handlers.HRAgentFacade") as mock_facade:
            mock_facade.register_candidate = MagicMock()
            await handle_message(mock_update, mock_context)

            mock_update.message.reply_text.assert_called()

if __name__ == "__main__":
    pytest.main(["-v"])
