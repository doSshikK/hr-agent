"""
app/db/survey_db.py
Модуль для работы с опросами NPS и Pulse в базе данных (PostgreSQL)
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.db.postgres_connector import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def init_db() -> None:
    """Создаёт таблицы, индексы в БД опросов (PostgreSQL)"""

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('nps', 'pulse')),
                questions TEXT NOT NULL,
                department TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id SERIAL PRIMARY KEY,
                survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
                respondent_name TEXT,
                respondent_email TEXT,
                answers TEXT,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_responses_survey ON responses(survey_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_surveys_status ON surveys(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_surveys_type ON surveys(type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at)")

        conn.commit()

    logger.info(f"✅ База данных опросов инициализирована (PostgreSQL)")


def _get_default_questions(survey_type: str) -> List[Dict[str, Any]]:
    if survey_type == "nps":
        return [
            {"id": "nps_score", "text": "Насколько вероятно, что вы порекомендуете компанию?", "type": "scale", "min": 0, "max": 10},
            {"id": "feedback", "text": "Что можно улучшить?", "type": "text"}
        ]
    elif survey_type == "pulse":
        return [
            {"id": "satisfaction", "text": "Насколько вы удовлетворены своей работой?", "type": "scale", "min": 1, "max": 5},
            {"id": "energy", "text": "Какой у вас уровень энергии на работе?", "type": "scale", "min": 1, "max": 5},
            {"id": "feedback", "text": "Что вас радует или огорчает?", "type": "text"}
        ]
    else:
        raise ValueError("Тип опроса должен быть 'nps' или 'pulse'")


def _row_to_survey_dict(colnames, row) -> Dict[str, Any]:
    """Преобразует строку БД в словарь опроса с правильной обработкой JSON"""
    if row is None:
        return None

    survey = dict(zip(colnames, row))

    questions = survey.get("questions")
    if questions and isinstance(questions, str):
        try:
            survey["questions"] = json.loads(questions)
        except json.JSONDecodeError:
            survey["questions"] = []
    elif not questions:
        survey["questions"] = []

    return survey


def _row_to_response_dict(colnames, row) -> Dict[str, Any]:
    """Преобразует строку БД в словарь ответа с правильной обработкой JSON"""
    if row is None:
        return None

    response = dict(zip(colnames, row))

    answers = response.get("answers")
    if answers and isinstance(answers, str):
        try:
            response["answers"] = json.loads(answers)
        except json.JSONDecodeError:
            response["answers"] = {}
    elif not answers:
        response["answers"] = {}

    return response


def create_survey(
    title: str,
    survey_type: str,
    department: Optional[str] = None,
    questions: Optional[List[Dict[str, Any]]] = None
) -> int:
    if survey_type not in ["nps", "pulse"]:
        raise ValueError("Тип опроса должен быть 'nps' или 'pulse'")

    if questions is None:
        questions = _get_default_questions(survey_type)

    questions_json = json.dumps(questions, ensure_ascii=False)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO surveys (title, type, questions, department)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (title, survey_type, questions_json, department))

        survey_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"✅ Создан опрос '{title}' (ID: {survey_id}, тип: {survey_type})")
        return survey_id


def get_survey(survey_id: int) -> Optional[Dict[str, Any]]:
    """Получает опрос по ID"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM surveys WHERE id = %s", (survey_id,))
        row = cur.fetchone()

        if not row:
            return None

        colnames = [desc[0] for desc in cur.description]
        return _row_to_survey_dict(colnames, row)


def get_all_surveys(active_only: bool = True) -> List[Dict[str, Any]]:
    """Получает список всех опросов"""
    with get_connection() as conn:
        cur = conn.cursor()

        if active_only:
            cur.execute("""
                SELECT * FROM surveys 
                WHERE status = 'active' 
                ORDER BY created_at DESC
            """)
        else:
            cur.execute("SELECT * FROM surveys ORDER BY created_at DESC")

        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        return [_row_to_survey_dict(colnames, row) for row in rows]


def update_survey_status(survey_id: int, status: str) -> bool:
    """Обновляет статус опроса"""
    if status not in ["active", "closed"]:
        raise ValueError("Статус должен быть 'active' или 'closed'")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE surveys 
            SET status = %s 
            WHERE id = %s
        """, (status, survey_id))

        conn.commit()

        if cur.rowcount > 0:
            logger.info(f"✅ Опрос ID {survey_id} изменён статус на {status}")
            return True
        return False


def delete_survey(survey_id: int) -> bool:
    """Удаляет опрос и все связанные ответы"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM surveys WHERE id = %s", (survey_id,))
        conn.commit()

        if cur.rowcount > 0:
            logger.info(f"🗑️ Удалён опрос ID: {survey_id}")
            return True
        return False


def delete_all_surveys() -> bool:
    """Удаляет все опросы и все ответы на них."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM responses")
            cur.execute("DELETE FROM surveys")
            conn.commit()
        logger.info("✅ Все опросы удалены")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления всех опросов: {e}")
        return False


def submit_response(
    survey_id: int,
    answers: Dict[str, Any],
    respondent_name: Optional[str] = None,
    respondent_email: Optional[str] = None,
    feedback: Optional[str] = None
) -> int:
    answers_json = json.dumps(answers, ensure_ascii=False)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO responses (survey_id, respondent_name, respondent_email, answers, feedback)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (survey_id, respondent_name, respondent_email, answers_json, feedback))

        response_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"✅ Сохранён ответ на опрос ID {survey_id} (response_id: {response_id})")
        return response_id


def get_responses(survey_id: int) -> List[Dict[str, Any]]:
    """Получает все ответы на опрос"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM responses 
            WHERE survey_id = %s 
            ORDER BY created_at DESC
        """, (survey_id,))

        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        return [_row_to_response_dict(colnames, row) for row in rows]


def get_response_count(survey_id: int) -> int:
    """Возвращает количество ответов на опрос"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM responses WHERE survey_id = %s", (survey_id,))
        result = cur.fetchone()
        return result[0] if result else 0


def analyze_survey_results(survey_id: int) -> Dict[str, Any]:
    survey = get_survey(survey_id)
    if not survey:
        return {"error": "Опрос не найден"}

    responses = get_responses(survey_id)

    if not responses:
        return {"error": "Нет ответов"}

    scores: Dict[str, List[float]] = {}
    feedbacks: List[str] = []

    for response in responses:
        answers = response.get("answers", {})

        for key, value in answers.items():
            if isinstance(value, (int, float)):
                scores.setdefault(key, []).append(float(value))

        if response.get("feedback"):
            feedbacks.append(response["feedback"])

    result: Dict[str, Any] = {
        "survey_title": survey["title"],
        "survey_type": survey["type"],
        "total_responses": len(responses),
        "feedbacks": feedbacks[:5],
        "generated_at": datetime.now().isoformat()
    }

    if survey["type"] == "nps" and "nps_score" in scores:
        nps_values = scores["nps_score"]
        total = len(nps_values)

        promoters = sum(1 for x in nps_values if x >= 9)
        passives = sum(1 for x in nps_values if 7 <= x <= 8)
        detractors = sum(1 for x in nps_values if x <= 6)

        nps_score = int(((promoters - detractors) / total) * 100) if total else 0

        result.update({
            "nps_score": nps_score,
            "promoters": promoters,
            "passives": passives,
            "detractors": detractors,
            "average_score": round(sum(nps_values) / total, 2)
        })

    else:
        for key, vals in scores.items():
            if vals:
                result[key] = {
                    "average": round(sum(vals) / len(vals), 2),
                    "min": min(vals),
                    "max": max(vals),
                    "count": len(vals)
                }

    return result


def get_survey_summary(survey_id: int) -> Dict[str, Any]:
    """Возвращает краткую сводку по опросу"""
    survey = get_survey(survey_id)
    if not survey:
        return {"error": "Опрос не найден"}

    response_count = get_response_count(survey_id)

    return {
        "id": survey["id"],
        "title": survey["title"],
        "type": survey["type"],
        "department": survey.get("department"),
        "status": survey["status"],
        "created_at": survey["created_at"],
        "response_count": response_count,
        "questions_count": len(survey.get("questions", []))
    }


def export_survey_results(survey_id: int, file_path: str) -> bool:
    results = analyze_survey_results(survey_id)

    if "error" in results:
        logger.error(f"Не удалось экспортировать опрос {survey_id}: {results['error']}")
        return False

    responses = get_responses(survey_id)
    results["full_responses"] = responses

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Результаты опроса {survey_id} экспортированы в {file_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при экспорте: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МОДУЛЯ SURVEY_DB (PostgreSQL)")
    print("=" * 60)

    init_db()

    print("\n📝 1. Создание NPS опроса...")
    nps_id = create_survey(
        title="NPS опрос Q1 2026",
        survey_type="nps",
        department="IT"
    )
    print(f"   ✅ Создан NPS опрос с ID: {nps_id}")

    print("\n📝 2. Создание Pulse опроса...")
    pulse_id = create_survey(
        title="Pulse опрос Март 2026",
        survey_type="pulse",
        department="HR"
    )
    print(f"   ✅ Создан Pulse опрос с ID: {pulse_id}")

    print("\n📝 3. Добавление ответов на NPS опрос...")
    submit_response(nps_id, {"nps_score": 10}, respondent_name="Иван Иванов", feedback="Отлично!")
    submit_response(nps_id, {"nps_score": 9}, respondent_name="Петр Петров", feedback="Хорошо")
    submit_response(nps_id, {"nps_score": 7}, respondent_name="Сидор Сидоров", feedback="Нормально")
    submit_response(nps_id, {"nps_score": 4}, respondent_name="Анна Аннова", feedback="Есть проблемы")
    print(f"   ✅ Добавлено 4 ответа")

    print("\n📝 4. Добавление ответов на Pulse опрос...")
    submit_response(pulse_id, {"satisfaction": 5, "energy": 4, "feedback": "Отлично!"})
    submit_response(pulse_id, {"satisfaction": 4, "energy": 3, "feedback": "Хорошо"})
    submit_response(pulse_id, {"satisfaction": 3, "energy": 2, "feedback": "Могло быть лучше"})
    print(f"   ✅ Добавлено 3 ответа")

    print("\n📊 5. Анализ NPS опроса:")
    nps_results = analyze_survey_results(nps_id)
    print(f"   Всего ответов: {nps_results['total_responses']}")
    print(f"   NPS Score: {nps_results.get('nps_score', 'N/A')}")
    print(f"   Промоутеры: {nps_results.get('promoters', 0)}")
    print(f"   Нейтралы: {nps_results.get('passives', 0)}")
    print(f"   Критики: {nps_results.get('detractors', 0)}")

    print("\n📊 6. Анализ Pulse опроса:")
    pulse_results = analyze_survey_results(pulse_id)
    print(f"   Всего ответов: {pulse_results['total_responses']}")
    print(f"   Удовлетворённость работой: {pulse_results.get('satisfaction', {}).get('average', 'N/A')}")
    print(f"   Уровень энергии: {pulse_results.get('energy', {}).get('average', 'N/A')}")

    print("\n📋 7. Краткая сводка:")
    summary = get_survey_summary(nps_id)
    print(f"   Опрос: {summary['title']}")
    print(f"   Ответов: {summary['response_count']}")

    print("\n📋 8. Все опросы:")
    all_surveys = get_all_surveys(active_only=False)
    for s in all_surveys:
        print(f"   #{s['id']}: {s['title']} ({s['type']}) - {s['status']}")

    print("\n✅ Все тесты пройдены!")
