"""
app/db/conversation_db.py
Хранение истории взаимодействия пользователя с HR-ботом.
"""

import json
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.db.postgres_connector import get_connection

logger = get_logger(__name__)


def init_conversation_db() -> None:
    """Создаёт таблицу истории диалога. Безопасно вызывать многократно."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id          SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content     TEXT NOT NULL,
                metadata    JSONB,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_history_user_created
            ON conversation_history(telegram_id, created_at DESC)
        """)
        conn.commit()


def save_conversation_message(
    telegram_id: int,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Сохраняет одно сообщение диалога."""
    if not telegram_id or not content:
        return

    try:
        init_conversation_db()
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO conversation_history (telegram_id, role, content, metadata)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (
                    telegram_id,
                    role,
                    content[:8000],
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Не удалось сохранить историю диалога: {e}")


def get_recent_conversation_history(telegram_id: int, limit: int = 10) -> List[Dict[str, str]]:
    """Возвращает последние сообщения в формате OpenAI messages."""
    if not telegram_id:
        return []

    try:
        init_conversation_db()
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT role, content
                FROM conversation_history
                WHERE telegram_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (telegram_id, limit),
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.warning(f"Не удалось получить историю диалога: {e}")
        return []

    messages = [{"role": role, "content": content} for role, content in reversed(rows)]
    return [m for m in messages if m["role"] in {"user", "assistant", "system"}]

