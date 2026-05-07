"""
app/db/postgres_connector.py
Пул соединений PostgreSQL с health check и авто-переподключением.
"""

import time
import psycopg2
from psycopg2 import pool, OperationalError
from contextlib import contextmanager
from typing import Optional

from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

_connection_pool: Optional[pool.ThreadedConnectionPool] = None

_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SEC = 2.0


def _build_pool() -> pool.ThreadedConnectionPool:
    """Создаёт ThreadedConnectionPool (потокобезопасен, восстанавливает соединения)."""
    return pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        connect_timeout=10,
        options="-c statement_timeout=30000",   # 30 сек макс на запрос
    )


def init_connection_pool() -> None:
    """
    Инициализирует пул соединений.
    Вызывается один раз при старте приложения из main.py.
    Поднимает исключение если PostgreSQL недоступен (fail-fast).
    """
    global _connection_pool
    last_error: Optional[Exception] = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            _connection_pool = _build_pool()
            _health_check()
            logger.info("✅ PostgreSQL connection pool initialized")
            return
        except Exception as e:
            last_error = e
            logger.warning(f"PostgreSQL attempt {attempt}/{_RETRY_ATTEMPTS} failed: {e}")
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SEC)

    raise ConnectionError(
        f"Не удалось подключиться к PostgreSQL после {_RETRY_ATTEMPTS} попыток: {last_error}"
    ) from last_error


def _health_check() -> None:
    """Проверяет живость пула через SELECT 1."""
    conn = _connection_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        _connection_pool.putconn(conn)


def _ensure_pool() -> None:
    """
    Гарантирует наличие рабочего пула.
    Если пул упал (broken connections) — пересоздаёт его.
    """
    global _connection_pool
    if _connection_pool is None:
        logger.warning("Connection pool not initialized — creating on demand")
        init_connection_pool()
        return

    try:
        _health_check()
    except Exception as e:
        logger.warning(f"Pool health check failed ({e}), recreating pool...")
        try:
            _connection_pool.closeall()
        except Exception:
            pass
        _connection_pool = None
        init_connection_pool()


@contextmanager
def get_connection():
    """
    Контекстный менеджер: берёт соединение из пула, коммитит при успехе,
    откатывает при ошибке, возвращает в пул в любом случае.
    При обрыве соединения делает один retry с пересозданием пула.
    """
    _ensure_pool()

    conn = None
    for attempt in range(2):          # 1 попытка + 1 retry
        try:
            conn = _connection_pool.getconn()
            if conn.closed:
                _connection_pool.putconn(conn, close=True)
                conn = None
                _ensure_pool()
                conn = _connection_pool.getconn()

            yield conn
            conn.commit()
            return
        except OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                    _connection_pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = None
            if attempt == 0:
                logger.warning(f"DB connection lost ({e}), retrying...")
                _ensure_pool()
                continue
            raise
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn and not conn.closed:
                try:
                    _connection_pool.putconn(conn)
                except Exception:
                    pass


@contextmanager
def get_cursor():
    """Удобный шорткат: курсор с автоматическим коммитом через get_connection."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
