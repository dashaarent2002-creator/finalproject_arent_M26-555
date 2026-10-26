"""Настройка логирования: формат, уровень, ротация файлов.

Формат выбран строковый (человекочитаемый):
    INFO 2025-10-09T12:05:22 BUY user_id=1 currency='BTC' amount=0.0500 ...
Ротация — по размеру файла (RotatingFileHandler).
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

ACTIONS_LOGGER = "valutatrade.actions"
PARSER_LOGGER = "valutatrade.parser"
ACTIONS_LOG_FILE = "actions.log"
PARSER_LOG_FILE = "parser.log"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
CONSOLE_FORMAT = "%(levelname)s: %(message)s"

_configured = False


def _file_handler(filename: str) -> RotatingFileHandler:
    """Файловый обработчик с ротацией по размеру."""
    settings = SettingsLoader()
    log_dir = settings.get("log_dir")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(log_dir, filename),
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(settings.get("log_format"), DATE_FORMAT))
    return handler


def setup_logging() -> None:
    """Настраивает логгеры один раз за запуск.

    actions — только в файл logs/actions.log (операции пользователей);
    parser  — в файл logs/parser.log и в консоль (ход обновления курсов).
    """
    global _configured
    if _configured:
        return
    level = SettingsLoader().get("log_level", "INFO")

    actions_logger = logging.getLogger(ACTIONS_LOGGER)
    actions_logger.setLevel(level)
    actions_logger.addHandler(_file_handler(ACTIONS_LOG_FILE))
    actions_logger.propagate = False

    parser_logger = logging.getLogger(PARSER_LOGGER)
    parser_logger.setLevel(level)
    parser_logger.addHandler(_file_handler(PARSER_LOG_FILE))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    parser_logger.addHandler(console)
    parser_logger.propagate = False

    _configured = True
