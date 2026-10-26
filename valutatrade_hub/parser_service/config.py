"""Конфигурация Parser Service: API, списки валют, пути, таймауты."""

import os
from dataclasses import dataclass, field

from valutatrade_hub.infra.settings import SettingsLoader

API_KEY_ENV = "EXCHANGERATE_API_KEY"
ENV_FILE = ".env"


def load_api_key() -> str | None:
    """Ключ ExchangeRate-API: из переменной окружения или из файла .env.

    Файл .env добавлен в .gitignore, поэтому ключ не попадает в репозиторий.
    """
    key = os.getenv(API_KEY_ENV)
    if key:
        return key.strip()
    if not os.path.exists(ENV_FILE):
        return None
    with open(ENV_FILE, encoding="utf-8") as file:
        for line in file:
            name, _, value = line.strip().partition("=")
            if name.strip() == API_KEY_ENV and value.strip():
                return value.strip().strip("'\"")
    return None


@dataclass
class ParserConfig:
    """Все изменяемые параметры Parser Service в одном месте."""

    # Ключ загружается из окружения / .env, а не хранится в коде
    EXCHANGERATE_API_KEY: str | None = field(default_factory=load_api_key)

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Валюты
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # Пути (берутся из SettingsLoader, чтобы Core и Parser читали одни файлы)
    RATES_FILE_PATH: str = field(
        default_factory=lambda: SettingsLoader().get("rates_file")
    )
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: SettingsLoader().get("history_file")
    )

    # Сеть и расписание
    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL_SECONDS: int = 300
