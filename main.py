#!/usr/bin/env python3
"""
HR Agent - Главная точка входа
"""

import sys
from pathlib import Path

from app.core.config import settings
from app.core.logger import setup_logger, get_logger

logger = get_logger(__name__)


def setup_directories():
    """Создаёт необходимые директории"""
    directories = [
        "logs",
    ]
    
    for directory in directories:
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)


def check_environment() -> bool:
    """Проверяет наличие необходимых переменных окружения"""
    missing = []
    
    if not settings.openrouter_api_key or settings.openrouter_api_key == "your_key_here":
        missing.append("OPENROUTER_API_KEY")
    
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_token_here":
        missing.append("TELEGRAM_BOT_TOKEN")
    
    if missing:
        logger.error(f"Отсутствуют переменные: {', '.join(missing)}")
        logger.error("Создайте файл .env на основе .env.example")
        return False
    
    return True


def init_databases() -> None:
    """
    Инициализирует соединение с PostgreSQL и создаёт все таблицы.

    Fail-fast: если PostgreSQL недоступен — поднимаем исключение сразу,
    а не позволяем боту стартовать и падать на первом запросе.
    """
    try:
        from app.db.postgres_connector import init_connection_pool
        init_connection_pool()
        logger.info("✅ Пул соединений PostgreSQL инициализирован")
    except Exception as e:
        logger.critical(f"❌ Не удалось подключиться к PostgreSQL: {e}")
        logger.critical("Убедитесь, что PostgreSQL запущен и параметры в .env верны.")
        raise SystemExit(1) from e   # fail-fast: бессмысленно стартовать без БД

    schema_steps = [
        ("app.db.candidate_db", "init_db", "кандидатов"),
        ("app.db.jobs_db",      "init_db", "вакансий"),
        ("app.db.survey_db",    "init_db", "опросов"),
    ]
    for module_path, func_name, label in schema_steps:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            getattr(mod, func_name)()
            logger.info(f"✅ БД {label} инициализирована")
        except Exception as e:
            logger.error(f"⚠️ Ошибка инициализации БД {label}: {e}")


def start_background_services():
    """Запускает фоновые сервисы (мониторинг почты и уведомления) (ДОБАВЛЕНО)"""
    
    if settings.email_user and settings.email_password:
        try:
            from app.utils.email_parser import start_email_monitoring
            start_email_monitoring()
            logger.info("📧 Мониторинг почты запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга почты: {e}")
    else:
        logger.info("📧 Мониторинг почты не настроен (EMAIL_USER или EMAIL_PASSWORD не заданы)")
    
    if settings.hr_telegram_id and settings.hr_telegram_id != 0:
        try:
            from app.utils.notification_sender import start_notification_worker
            start_notification_worker()
            logger.info("📨 Notification worker запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска notification worker: {e}")
    else:
        logger.info("📨 Notification worker не запущен (HR_TELEGRAM_ID не задан)")
    

def start_telegram_bot():
    """Запускает Telegram бота"""
    try:
        from app.bot.telegram_bot import main as run_bot
        logger.info("🤖 Запуск Telegram бота...")
        run_bot()
    except Exception as e:
        logger.error(f"Ошибка запуска Telegram бота: {e}")
        raise


def main():
    """Запуск HR Agent"""
    
    setup_logger(level=settings.log_level, log_file="logs/hr_agent.log")
    
    logger.info("🚀 Запуск HR Agent")
    
    setup_directories()
    
    from app.core.config import validate_settings
    cfg_valid, cfg_errors = validate_settings()
    if not cfg_valid:
        for err in cfg_errors:
            logger.warning(f"⚠️ Конфиг: {err}")

    if not check_environment():
        print("\n⚠️ Ошибка конфигурации!")
        print("   1. Создайте файл .env на основе .env.example")
        print("   2. Укажите OPENROUTER_API_KEY")
        print("   3. Укажите TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    
    init_databases()
    
    start_background_services()
    
    try:
        print("\n✅ Бот запущен! Найдите его в Telegram и отправьте /start")
        print("📋 Доступные функции:")
        print("   • Поиск кандидатов по любым критериям")
        print("   • Генерация тестовых заданий для любых профессий")
        print("   • Создание планов онбординга")
        print("   • Проведение NPS и Pulse опросов")
        print("   • Управление собеседованиями")
        print("   • Интерактивный онбординг с напоминаниями")
        print("")
        print("⏹️ Для остановки нажмите Ctrl+C\n")
        start_telegram_bot()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
        print("\n\n👋 Бот остановлен. До свидания!")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
