"""Хранилище Parser Service: история (exchange_rates.json) и кеш (rates.json)."""

from valutatrade_hub.core.utils import parse_iso
from valutatrade_hub.infra.database import read_json, write_json_atomic
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Чтение и атомарная запись файлов курсов."""

    def __init__(self, config: ParserConfig):
        self.rates_path = config.RATES_FILE_PATH
        self.history_path = config.HISTORY_FILE_PATH

    def read_cache(self) -> dict:
        """Текущий кеш rates.json: {'pairs': {...}, 'last_refresh': ...}."""
        data = read_json(self.rates_path, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("pairs", {})
        return data

    def update_cache(self, pairs: dict, last_refresh: str) -> int:
        """Обновляет кеш. Новое значение «побеждает», только если оно свежее.

        Возвращает количество обновлённых пар.
        """
        cache = self.read_cache()
        updated = 0
        for key, entry in pairs.items():
            current = cache["pairs"].get(key)
            if current is None or parse_iso(entry["updated_at"]) >= parse_iso(
                current["updated_at"]
            ):
                cache["pairs"][key] = entry
                updated += 1
        cache["source"] = "ParserService"
        cache["last_refresh"] = last_refresh
        write_json_atomic(self.rates_path, cache)
        return updated

    def append_history(self, records: list[dict]) -> int:
        """Дописывает замеры в историю, пропуская уже существующие id."""
        history = read_json(self.history_path, [])
        if not isinstance(history, list):
            history = []
        known_ids = {record.get("id") for record in history}
        new_records = [record for record in records if record["id"] not in known_ids]
        if new_records:
            write_json_atomic(self.history_path, history + new_records)
        return len(new_records)
