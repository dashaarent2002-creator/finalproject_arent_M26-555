"""Singleton DatabaseManager — абстракция над JSON-хранилищем."""

import json
import os
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader

TMP_SUFFIX = ".tmp"


class DatabaseManager:
    """Читает и атомарно записывает JSON-файлы проекта.

    Singleton через __new__ (как и SettingsLoader) — так в приложении
    существует ровно один объект доступа к данным.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = SettingsLoader()
        return cls._instance

    def path_for(self, name: str) -> str:
        """Путь к файлу по ключу настроек: users, portfolios, rates, history."""
        return self._settings.get(f"{name}_file")

    def read(self, name: str, default: Any) -> Any:
        """Читает JSON-файл. Если файла нет или он пустой — возвращает default."""
        return read_json(self.path_for(name), default)

    def write(self, name: str, data: Any) -> None:
        """Атомарно записывает данные в JSON-файл."""
        write_json_atomic(self.path_for(name), data)


def read_json(path: str, default: Any) -> Any:
    """Безопасно читает JSON-файл."""
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path: str, data: Any) -> None:
    """Пишет во временный файл, затем заменяет основной (tmp → rename)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = path + TMP_SUFFIX
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    os.replace(tmp_path, path)
