"""
app/core/logger.py
Настройка логирования для HR Agent
"""

import sys
from pathlib import Path
from loguru import logger

_initialized = False


def setup_logger(
    level: str = "INFO",
    log_file: str = "logs/hr_agent.log",
    rotation: str = "1 day",
    retention: str = "30 days",
    compression: str = "zip",
    console_output: bool = True,
    colorize: bool = True
) -> logger:

    global _initialized
    
    logger.remove()
    
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    
    if console_output:
        logger.add(
            sys.stdout,
            format=console_format,
            level=level.upper(),
            colorize=colorize,
            backtrace=True,
            diagnose=True
        )
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            format=file_format,
            level=level.upper(),
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            backtrace=True,
            diagnose=False  # Отключаем diagnose в файле для безопасности
        )
    
    _initialized = True
    
    logger.info(f"✅ Логирование настроено (уровень: {level.upper()})")
    
    return logger


def get_logger(name: str = None) -> logger:

    if not _initialized:
        setup_logger()
    
    if name:
        return logger.bind(name=name)
    return logger


def get_module_logger(module_name: str) -> logger:

    return get_logger(name=module_name)


if __name__ == "__main__":
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ЛОГГЕРА")
    print("=" * 60)
    
    setup_logger(level="DEBUG")
    
    test_logger = get_logger("test")
    
    test_logger.debug("Это DEBUG сообщение")
    test_logger.info("Это INFO сообщение")
    test_logger.warning("Это WARNING сообщение")
    test_logger.error("Это ERROR сообщение")
    
    module_logger = get_module_logger("my_module")
    module_logger.info("Сообщение от модуля my_module")
    
    result = test_function(5, 3)
    test_logger.info(f"Результат test_function: {result}")
    
    print("\n✅ Тестирование завершено! Смотрите вывод выше.")
