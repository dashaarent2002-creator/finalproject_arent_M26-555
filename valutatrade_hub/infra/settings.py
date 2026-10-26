"""Singleton SettingsLoader — единая точка конфигурации приложения."""

import os
import tomllib
from typing import Any

PYPROJECT_FILE = "pyproject.toml"
CONFIG_SECTION = "valutatrade"

# Значения по умолчанию, если в pyproject.toml нет секции [tool.valutatrade]
DEFAULT_SETTINGS = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_level": "INFO",
    "log_format": "%(levelname)s %(asctime)s %(message)s",
    "log_max_bytes": 1_048_576,
    "log_backup_count": 5,
}


class SettingsLoader:
    """Загружает и кеширует конфигурацию проекта.

    Singleton реализован через __new__: это самый простой и читаемый способ —
    не нужен отдельный метакласс, а логика «один экземпляр» видна прямо в классе.
    Повторные вызовы SettingsLoader() и повторные импорты возвращают тот же объект.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        """Перечитывает конфигурацию из pyproject.toml."""
        settings = dict(DEFAULT_SETTINGS)
        settings.update(self._read_pyproject_section())
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение настройки по ключу."""
        return self._settings.get(key, default)

    @staticmethod
    def _read_pyproject_section() -> dict:
        """Читает секцию [tool.valutatrade] из pyproject.toml, если файл есть."""
        if not os.path.exists(PYPROJECT_FILE):
            return {}
        try:
            with open(PYPROJECT_FILE, "rb") as file:
                data = tomllib.load(file)
        except (OSError, tomllib.TOMLDecodeError):
            return {}
        return data.get("tool", {}).get(CONFIG_SECTION, {})


settings = SettingsLoader()
