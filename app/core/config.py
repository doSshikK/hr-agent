"""
app/core/config.py
Конфигурация приложения HR Agent
"""

from typing import List, Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""


    telegram_bot_token: str
    openrouter_api_key: str


    default_model: str = "qwen/qwen3.6-35b-a3b"
    llm_timeout: int = 180
    llm_max_retries: int = 3
    llm_temperature: float = 0.5


    log_level: str = "INFO"
    log_file: str = "logs/hr_agent.log"
    log_rotation: str = "1 day"
    log_retention: str = "30 days"


    data_dir: str = "data"
    database_path: str = "data/hr_agent.db"


    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "hr_agent"
    postgres_user: str = "hr_agent"
    postgres_password: str = ""


    email_host: str = "imap.mail.ru"
    email_port: int = 993
    email_user: str = ""
    email_password: str = ""

    hr_telegram_id: int = 0
    hr_ids: str = ""   # comma-separated list, парсится в hr_telegram_ids()


    interview_address: str = "г. Челябинск, ул. Ленина, 5, офис 301"
    interview_reminder_text: str = "Не забудьте паспорт и резюме!"
    interview_working_hours_start: str = "09:00"
    interview_working_hours_end: str = "18:00"
    interview_slot_interval_minutes: int = 60


    smtp_host: str = "smtp.mail.ru"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""


    default_match_skills_weight: float = 0.5
    default_match_exp_weight: float = 0.3
    default_match_position_weight: float = 0.2

    min_match_percent: int = 20
    fuzzy_match_threshold: int = 80


    telegram_request_timeout: int = 60
    telegram_max_message_length: int = 4096


    max_file_size_mb: int = 10
    supported_file_extensions: List[str] = [".pdf", ".docx"]


    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )


    @property
    def db_full_path(self) -> Path:
        """Путь к файлу БД (единый для всех модулей; используется только SQLite-fallback)"""
        return Path(self.database_path).resolve()

    @property
    def candidates_db_full_path(self) -> Path:
        return self.db_full_path

    @property
    def jobs_db_full_path(self) -> Path:
        return self.db_full_path

    @property
    def surveys_db_full_path(self) -> Path:
        return self.db_full_path

    @property
    def data_dir_path(self) -> Path:
        """Путь к директории данных"""
        return Path(self.data_dir).resolve()

    def get_weights_dict(self) -> dict:
        """Возвращает словарь весов для поиска"""
        return {
            "skills": self.default_match_skills_weight,
            "exp": self.default_match_exp_weight,
            "pos": self.default_match_position_weight,
        }

    def is_development(self) -> bool:
        """Проверяет, запущено ли приложение в режиме разработки"""
        return self.log_level.upper() == "DEBUG"

    def is_valid_file_extension(self, filename: str) -> bool:
        """Проверяет, поддерживается ли расширение файла"""
        ext = Path(filename).suffix.lower()
        return ext in self.supported_file_extensions

    @property
    def postgres_connection_string(self) -> str:
        """Строка подключения к PostgreSQL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


    def hr_telegram_ids(self) -> list[int]:
        """Возвращает список всех HR Telegram ID (первичный + дополнительные из HR_IDS)."""
        ids = set()
        if self.hr_telegram_id and self.hr_telegram_id != 0:
            ids.add(self.hr_telegram_id)
        for raw in self.hr_ids.split(","):
            raw = raw.strip()
            if raw.isdigit():
                ids.add(int(raw))
        return list(ids)

    def is_hr(self, telegram_id: int) -> bool:
        """Проверяет, является ли пользователь HR (поддерживает нескольких HR)."""
        return telegram_id in self.hr_telegram_ids()


settings = Settings()


def validate_settings() -> tuple[bool, List[str]]:
    """
    Проверяет корректность настроек
    
    Returns:
        tuple: (is_valid, errors_list)
    """
    errors = []

    if not settings.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN не задан в .env")
    elif len(settings.telegram_bot_token) < 30:
        errors.append("TELEGRAM_BOT_TOKEN некорректный")

    if not settings.openrouter_api_key:
        errors.append("OPENROUTER_API_KEY не задан в .env")
    elif not settings.openrouter_api_key.startswith("sk-or-"):
        errors.append("OPENROUTER_API_KEY некорректный")

    total_weight = (
        settings.default_match_skills_weight +
        settings.default_match_exp_weight +
        settings.default_match_position_weight
    )

    if abs(total_weight - 1.0) > 0.01:
        errors.append(f"Сумма весов должна быть 1.0, сейчас {total_weight}")

    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if settings.log_level.upper() not in valid_log_levels:
        errors.append("Некорректный LOG_LEVEL")

    if not 0 <= settings.min_match_percent <= 100:
        errors.append("min_match_percent должен быть 0-100")

    return len(errors) == 0, errors


if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА КОНФИГА")
    print("=" * 60)

    is_valid, errors = validate_settings()

    if is_valid:
        print("✅ Всё ок")
    else:
        for e in errors:
            print("❌", e)
