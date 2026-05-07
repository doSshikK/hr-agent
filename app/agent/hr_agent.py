"""
app/agent/hr_agent.py
HR Агент с поддержкой function calling
"""

import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from openai import OpenAI

from app.core.logger import get_logger
from app.core.config import settings
from app.agent.tools import TOOLS
from app.services.hr_facade import HRAgentFacade
from app.utils.file_parser import parse_resume
from app.utils.formatters import format_overall_statistics
from app.services.test_generator import format_test
from app.services.onboarding_generator import format_onboarding_plan
from app.services.candidate_service import check_candidate_exists

logger = get_logger(__name__)


def _handle_parse_resume(arguments: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Парсит резюме и сохраняет данные в сессию пользователя."""
    file_path = arguments.get("file_path")
    result = parse_resume(file_path)

    if "error" in result:
        return f"❌ Ошибка парсинга: {result['error']}"

    exists, existing = check_candidate_exists(result)
    logger.info(f"Результат проверки дубля: exists={exists}")

    output = [
        "📄 **РЕЗУЛЬТАТ ПАРСИНГА РЕЗЮМЕ**", "=" * 50, "",
        "👤 **Личные данные:**",
        f"   • Имя: {result.get('name', '—')}",
        f"   • Email: {result.get('email', '—')}",
        f"   • Телефон: {result.get('phone', '—')}",
        "",
        "💼 **Опыт работы:**",
        f"   • Общий опыт: {result.get('experience_years', 0)} лет",
        f"   • Последняя должность: {result.get('last_position', '—')}",
        f"   • Последняя компания: {result.get('last_company', '—')}",
        "",
        "🛠️ **Навыки:**",
    ]
    skills = result.get("skills", [])
    if skills:
        output.append(f"   • {', '.join(skills[:15])}")
        if len(skills) > 15:
            output.append(f"   • ... и ещё {len(skills) - 15} навыков")
    else:
        output.append("   • Навыки не найдены")
    output += ["", "=" * 50, ""]

    if exists:
        output += [
            "⚠️ **КАНДИДАТ УЖЕ ЕСТЬ В БАЗЕ!**",
            f"   • ID: {existing.get('id')}",
            f"   • Имя: {existing.get('name')}",
            f"   • Email: {existing.get('email')}",
            "",
            "📌 **Что делать?**",
            "   • Напишите 'обновить' — обновить данные кандидата",
            "   • Напишите 'нет' — пропустить",
            "   • Напишите 'добавить как нового' — создать дубликат",
        ]
    else:
        output += [
            "✅ **КАНДИДАТ НЕ НАЙДЕН В БАЗЕ**", "",
            "📌 **Что делать?**",
            "   • Напишите 'да' или 'добавить' — сохранить кандидата в базу",
            "   • Напишите 'нет' — пропустить",
        ]

    session_data["last_parsed_candidate"] = {"data": result, "file_path": arguments.get("file_path", "")}
    return "\n".join(output)


def _handle_save_candidate(arguments: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Сохраняет кандидата в БД. Берёт данные из аргументов или из сессии."""
    candidate_data = arguments.get("candidate_data", {})
    file_path = arguments.get("file_path", "")

    last_parsed = session_data.get("last_parsed_candidate")
    if not candidate_data and last_parsed:
        candidate_data = last_parsed.get("data", {})
        file_path = last_parsed.get("file_path", "")
        session_data.pop("last_parsed_candidate", None)

    exists, existing = check_candidate_exists(candidate_data)
    candidate_id = HRAgentFacade.save_candidate(candidate_data, file_path)

    if exists:
        logger.info(f"🔄 Обновление кандидата ID: {existing.get('id')}")
        return f"✅ **Кандидат ОБНОВЛЁН!** ID: {candidate_id}\n\nДанные кандидата успешно обновлены в базе."
    else:
        logger.info("➕ Добавление нового кандидата")
        return f"✅ **КАНДИДАТ ДОБАВЛЕН В БАЗУ!** ID: {candidate_id}\n\nКандидат успешно сохранён. Теперь он будет доступен в поиске."


def _handle_search_candidates(arguments: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Ищет кандидатов по критериям."""
    results = HRAgentFacade.search_candidates(
        skills=arguments.get("skills", []),
        min_experience=arguments.get("min_experience"),
        position=arguments.get("position"),
        top_n=100,
    )
    min_match = arguments.get("min_match_percent", 20)
    filtered = [r for r in results if r.get("match_percent", 0) >= min_match]

    if not filtered:
        return "😕 Кандидаты не найдены."

    session_data["last_candidates"] = filtered[:10]
    session_data["last_candidate"] = filtered[0]

    formatted = ["🔍 **РЕЗУЛЬТАТЫ ПОИСКА**", "=" * 40, ""]
    for i, cand in enumerate(filtered[:10], 1):
        pct = cand.get("match_percent", 0)
        emoji = "🏆" if pct >= 70 else ("📊" if pct >= 40 else "⚠️")
        formatted += [
            f"{emoji} **{i}. #{cand.get('id', '?')} — {cand.get('name', 'Без имени')}**",
            f"   • Совпадение: {pct}%",
            f"   • Опыт: {cand.get('experience_years', 0)} лет",
            f"   • Навыки: {', '.join(cand.get('skills', [])[:5])}",
            "",
        ]
    return "\n".join(formatted)


def _handle_match_candidates(arguments: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Подбирает топ-кандидатов для вакансии."""
    job_id = arguments.get("job_id")
    if not job_id:
        return "❌ Не указан ID вакансии"

    result = HRAgentFacade.match_candidates(job_id=job_id, top_n=arguments.get("top_n", 5))
    if "error" in result:
        return f"❌ {result['error']}"

    job = result.get("job", {})
    candidates = result.get("top_candidates", [])
    session_data["last_job"] = job
    if candidates:
        session_data["last_candidates"] = candidates[:10]
        session_data["last_candidate"] = candidates[0]
    if not candidates:
        return f"😕 Подходящих кандидатов для вакансии '{job.get('title', '—')}' не найдено."

    formatted = [f"🎯 **ТОП КАНДИДАТОВ ДЛЯ ВАКАНСИИ: {job.get('title', '—')}**", "=" * 50, ""]
    for i, cand in enumerate(candidates, 1):
        formatted += [
            f"{i}. **{cand.get('name', 'Без имени')}** — {cand.get('match_percent', 0)}% совпадение",
            f"   • Опыт: {cand.get('experience_years', 0)} лет",
            f"   • Навыки: {', '.join(cand.get('skills', [])[:5])}",
            "",
        ]
    return "\n".join(formatted)


def _find_candidate_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Находит кандидата по имени для agent tool без зависимости от bot-слоя."""
    candidates = HRAgentFacade.get_all_candidates_dict(limit=1000)
    name_lower = name.lower().strip()

    for cand in candidates:
        cand_name = (cand.get("name") or "").lower()
        if name_lower == cand_name or name_lower in cand_name or cand_name in name_lower:
            return cand

    return None


def _handle_prepare_interview_invite(arguments: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Готовит приглашение на собеседование и ждёт подтверждения HR."""
    candidate_id = arguments.get("candidate_id")
    candidate_name = arguments.get("candidate_name")
    position = arguments.get("position")

    if not candidate_id and candidate_name:
        pronouns = {"его", "ее", "её", "их", "этого кандидата", "кандидата"}
        if candidate_name.lower().strip() in pronouns:
            candidate_id = (session_data.get("last_candidate") or {}).get("id")

    if not candidate_id and not candidate_name:
        candidate_id = (session_data.get("last_candidate") or {}).get("id")

    if not position:
        position = (session_data.get("last_job") or {}).get("title")

    candidate = None
    if candidate_id:
        candidate = HRAgentFacade.get_candidate(int(candidate_id))
    elif candidate_name:
        candidate = _find_candidate_by_name(candidate_name)

    if not candidate:
        return "❌ Кандидат не найден. Уточните ID или имя кандидата."

    candidate_id = candidate.get("id")
    candidate_name = candidate.get("name", "Без имени")

    if candidate.get("interview_stage") in ["invited", "scheduled"]:
        return f"❌ Кандидат {candidate_name} уже приглашён на собеседование."

    session_data["pending_action"] = {
        "type": "invite_candidate_to_interview",
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "position": position,
    }

    position_text = f"\n• Должность: {position}" if position else ""
    return (
        "📅 **Подготовлено приглашение на собеседование**\n\n"
        f"• Кандидат: **{candidate_name}**\n"
        f"• ID: {candidate_id}"
        f"{position_text}\n\n"
        "Подтвердите отправку: напишите **да**, **подтвердить** или **отправить**.\n"
        "Чтобы отменить действие, напишите **нет** или **отмена**."
    )


def _handle_generate_test(arguments: Dict[str, Any], session_data: Dict[str, Any]) -> str:
    """Генерирует тестовое задание через LLM."""
    direction = arguments.get("direction", "backend")
    level = arguments.get("level", "middle")
    tech_stack = arguments.get("tech_stack", [])
    candidate_name = arguments.get("candidate_name")
    last_job = session_data.get("last_job") or {}

    if last_job and not tech_stack:
        tech_stack = last_job.get("skills", [])
    if last_job and not arguments.get("direction"):
        direction = "custom"
    if last_job and not candidate_name:
        candidate_name = last_job.get("title")
    valid_directions = [
        "it", "production", "construction", "logistics", "office",
        "sales", "marketing", "finance", "hr", "custom",
        "backend", "frontend", "fullstack", "devops", "mobile",
    ]
    if direction not in valid_directions:
        direction = "it"
    if level not in ("junior", "middle", "senior"):
        level = "middle"

    logger.info(f"Генерация теста: direction={direction}, level={level}")
    test = HRAgentFacade.generate_test(
        direction=direction,
        level=level,
        tech_stack=tech_stack,
        candidate_name=candidate_name,
    )
    if "error" in test:
        return f"❌ Ошибка: {test['error']}"
    return format_test(test)


def _handle_create_onboarding(arguments: Dict[str, Any], _session: Dict[str, Any]) -> str:
    """Генерирует план онбординга."""
    candidate_name = arguments.get("candidate_name")
    if not candidate_name:
        return "❌ Не указано имя сотрудника"

    plan = HRAgentFacade.generate_onboarding(
        candidate_name=candidate_name,
        candidate_email=arguments.get("candidate_email"),
        department=arguments.get("department", "development"),
        level=arguments.get("level"),
        start_date=arguments.get("start_date"),
    )
    return format_onboarding_plan(plan)


def _handle_create_survey(arguments: Dict[str, Any], _session: Dict[str, Any]) -> str:
    """Создаёт NPS или Pulse опрос."""
    title = arguments.get("title")
    survey_type = arguments.get("survey_type")
    if not title or not survey_type:
        return "❌ Не указано название или тип опроса"

    survey_id = HRAgentFacade.create_survey(
        title=title, survey_type=survey_type, department=arguments.get("department")
    )
    questions = (
        "1. Насколько вероятно, что вы порекомендуете компанию? (0-10)\n2. Что можно улучшить?"
        if survey_type == "nps"
        else "1. Удовлетворенность работой (1-5)\n2. Уровень энергии (1-5)\n3. Ваш фидбек"
    )
    return f"✅ **ОПРОС СОЗДАН!**\n\n• ID: {survey_id}\n• Тип: {survey_type.upper()}\n• Название: {title}\n\n**Вопросы:**\n{questions}"


def _handle_analyze_survey(arguments: Dict[str, Any], _session: Dict[str, Any]) -> str:
    """Анализирует результаты опроса."""
    survey_id = arguments.get("survey_id")
    if not survey_id:
        return "❌ Не указан ID опроса"

    results = HRAgentFacade.analyze_survey(survey_id)
    if "error" in results:
        return f"❌ Ошибка: {results['error']}"

    output = [f"📊 **РЕЗУЛЬТАТЫ ОПРОСА #{survey_id}**", "=" * 40, "",
              f"📋 Всего ответов: {results.get('total_responses', 0)}"]
    if results.get("survey_type") == "nps":
        nps = results.get("nps_score", 0)
        grade = ("🏆 Отлично!" if nps >= 70 else
                 "📊 Хорошо" if nps >= 50 else
                 "⚠️ Средне" if nps >= 30 else "🔴 Требует внимания")
        output += [
            f"🎯 **NPS Score:** {nps} ({grade})",
            f"🟢 Промоутеры (9-10): {results.get('promoters', 0)}",
            f"🟡 Нейтралы (7-8): {results.get('passives', 0)}",
            f"🔴 Критики (0-6): {results.get('detractors', 0)}",
        ]
    return "\n".join(output)


def _handle_list_jobs(arguments: Dict[str, Any], _session: Dict[str, Any]) -> str:
    """Возвращает список всех вакансий."""
    jobs = HRAgentFacade.get_all_jobs_dict(active_only=False)
    if not jobs:
        return "📭 Вакансий пока нет в базе."

    output = ["📋 **СПИСОК ВАКАНСИЙ**", "=" * 40, ""]
    for job in jobs:
        s = "✅" if job.get("status") == "active" else "📦"
        lv = job.get("level", "")
        l = "🟢" if lv == "junior" else ("🟡" if lv == "middle" else "🔴")
        output.append(f"{s} {l} **#{job['id']}: {job['title']}** ({lv or '—'})")
        output.append(f"   • Опыт: {job.get('experience', 0)} лет")
        if job.get("skills"):
            output.append(f"   • Навыки: {', '.join(job['skills'][:5])}")
        output.append("")
    return "\n".join(output)


def _handle_list_candidates(arguments: Dict[str, Any], _session: Dict[str, Any]) -> str:
    """Возвращает список кандидатов."""
    candidates = HRAgentFacade.get_all_candidates_dict(limit=1000)
    if not candidates:
        return "📭 Кандидатов пока нет в базе."

    output = ["📋 **СПИСОК КАНДИДАТОВ**", "=" * 40, ""]
    for i, cand in enumerate(candidates[:20], 1):
        output.append(f"{i}. **#{cand.get('id', '?')}** — {cand.get('name', 'Без имени')}")
        output.append(f"   • Опыт: {cand.get('experience_years', 0)} лет")
        if cand.get("last_position"):
            output.append(f"   • Должность: {cand['last_position']}")
        if cand.get("skills"):
            output.append(f"   • Навыки: {', '.join(cand.get('skills', [])[:4])}")
        output.append("")
    if len(candidates) > 20:
        output.append(f"... и ещё {len(candidates) - 20} кандидатов")
    return "\n".join(output)


def _handle_get_statistics(arguments: Dict[str, Any], _session: Dict[str, Any]) -> str:
    """Возвращает общую статистику."""
    return format_overall_statistics(HRAgentFacade.get_statistics())


_TOOL_HANDLERS: Dict[str, Any] = {
    "parse_resume":            _handle_parse_resume,
    "save_candidate_to_db":    _handle_save_candidate,
    "search_candidates":       _handle_search_candidates,
    "match_candidates_to_job": _handle_match_candidates,
    "prepare_interview_invite": _handle_prepare_interview_invite,
    "generate_test_task":      _handle_generate_test,
    "create_onboarding_plan":  _handle_create_onboarding,
    "create_survey":           _handle_create_survey,
    "analyze_survey":          _handle_analyze_survey,
    "list_jobs":               _handle_list_jobs,
    "list_candidates":         _handle_list_candidates,
    "get_statistics":          _handle_get_statistics,
}


def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    session_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Маршрутизирует вызов инструмента к соответствующему обработчику.

    session_data — изолированный словарь сессии конкретного пользователя
    (context.user_data из PTB). Передаётся в каждый обработчик для хранения
    промежуточного состояния без глобальных переменных.
    """
    if session_data is None:
        session_data = {}

    logger.info(f"🔧 Инструмент: {tool_name} | аргументы: {list(arguments.keys())}")

    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"❌ Неизвестный инструмент: {tool_name}"

    try:
        return handler(arguments, session_data)
    except Exception as e:
        logger.error(f"Ошибка в обработчике {tool_name}: {e}", exc_info=True)
        return f"❌ Ошибка при выполнении '{tool_name}': {str(e)}"


def get_llm_client() -> OpenAI:

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY не найден в настройках")
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries
    )


class HRAgent:
    def __init__(self, llm_client: OpenAI = None, model: str = None):
        """
        DI через конструктор — можно подменить зависимости для тестов.
        
        Args:
            llm_client: OpenAI клиент (если None — создаётся через get_llm_client)
            model: Название модели (если None — берётся из settings.default_model)
        """
        self.client = llm_client or get_llm_client()
        self.model = model or settings.default_model
        self.system_prompt = """Ты — универсальный HR-агент, интеллектуальный помощник для автоматизации подбора персонала и адаптации сотрудников в любой компании.

Твоя задача — помогать HR-специалистам и руководителям в компаниях любого профиля: производство, строительство, логистика, IT, торговля, сфера услуг, медицина, образование и другие.

**Твои возможности:**
- 📄 Парсинг резюме (PDF/DOCX) с полным выводом информации
- 🔍 Поиск кандидатов по любым критериям: профессия, навыки, опыт, компания, имя
- 🎯 Matching кандидатов к вакансиям с расчётом % совпадения
- 📝 Генерация тестовых заданий (для IT, производства, строительства, логистики, офиса, продаж и других сфер)
- 📋 Создание планов онбординга (9 отделов: разработка, аналитика, менеджмент, маркетинг, продажи, HR, финансы, юридический отдел, дизайн)
- 📊 Проведение NPS и Pulse опросов
- 📅 Управление собеседованиями (слоты, приглашения, офферы)

**ВАЖНЫЕ ПРАВИЛА:**
1. После парсинга резюме покажи пользователю ВСЮ информацию о кандидате
2. Затем спроси, хочет ли пользователь добавить кандидата в базу
3. Если пользователь говорит "да", "добавить", "сохрани" — вызови инструмент save_candidate_to_db
4. Если пользователь говорит "обновить" — вызови save_candidate_to_db
5. Отвечай подробно, используй эмодзи, форматируй ответы
6. Не ограничивайся только IT-сферой — поддерживай любые профессии и отрасли
7. Если пользователь просит найти кандидата и пригласить его на собеседование, сначала вызови search_candidates, выбери самого подходящего кандидата, затем вызови prepare_interview_invite. Не говори, что приглашение отправлено, пока HR не подтвердит отправку.
8. Действия с внешним эффектом выполняются только через подтверждение HR. Для приглашения на собеседование prepare_interview_invite только готовит действие и просит подтверждение.
9. Если пользователь пишет "его", "её", "этого кандидата" — используй последнего найденного или показанного кандидата из истории/сессии.
10. Если пользователь пишет "эта вакансия", "этой вакансии" — используй последнюю показанную или подобранную вакансию из истории/сессии.

**Ты — профессиональный HR-ассистент для любой компании. Будь вежливым и полезным!"""
    
    def chat(
        self,
        user_message: str,
        history: List[Dict] = None,
        session_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Обрабатывает сообщение пользователя.

        session_data передаётся в execute_tool для хранения промежуточных
        данных парсинга резюме без глобальных переменных.
        """
        if session_data is None:
            session_data = {}

        messages = [{"role": "system", "content": self.system_prompt}]

        if history:
            messages.extend(history[-10:])

        messages.append({"role": "user", "content": user_message})

        MAX_ITERATIONS = 8  # достаточно для цепочек tool calling
        last_error: Optional[Exception] = None

        for iteration in range(MAX_ITERATIONS):
            try:
                logger.info(f"🔄 Итерация {iteration + 1}/{MAX_ITERATIONS}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=settings.llm_temperature,
                    timeout=settings.llm_timeout,
                )

                message = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                if finish_reason == "stop" or not message.tool_calls:
                    return message.content or "Я не могу ответить на этот запрос."
                
                if finish_reason == "length":
                    logger.warning("⚠️ Ответ LLM был обрезан из-за ограничения длины")
                    return (message.content or "") + "\n\n⚠️ *Ответ был обрезан из-за ограничения длины. Попробуйте уточнить запрос.*"

                messages.append(message.model_dump())

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"Невалидный JSON аргументов инструмента {tool_name}: {e}")
                        arguments = {}

                    result = execute_tool(tool_name, arguments, session_data)

                    if tool_name in ["list_candidates", "list_jobs", "get_statistics", "prepare_interview_invite"]:
                        return result

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            except Exception as e:
                last_error = e
                logger.error(f"❌ Ошибка в итерации {iteration + 1}: {e}")
                time.sleep(0.5)
                continue

        if last_error:
            return f"❌ Сервис временно недоступен. Попробуйте позже.\nОшибка: {str(last_error)}"

        return "⚠️ Не удалось завершить запрос. Попробуйте уточнить запрос."


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ HR_AGENT")
    print("=" * 60)
    
    agent = HRAgent()
    
    print("\n🤖 HR-агент создан и готов к работе!")
    print(f"   Модель: {agent.model}")
    print(f"   Доступно инструментов: {len(TOOLS)}")
    
    print("\n✅ Готов к запуску через Telegram бота!")
