"""Клиенты внешних API с единым интерфейсом fetch_rates()."""

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

HTTP_OK = 200
MS_IN_SECOND = 1000
STATUS_MESSAGES = {
    401: "неверный или отсутствующий API-ключ (401)",
    403: "доступ запрещён, проверьте API-ключ (403)",
    404: "ресурс не найден (404)",
    429: "превышен лимит запросов, попробуйте позже (429)",
}


class BaseApiClient(ABC):
    """Общий интерфейс клиента: fetch_rates() → {'BTC_USD': 59337.21, ...}."""

    name = "BaseApi"
    source_key = ""

    def __init__(self, config: ParserConfig):
        self.config = config
        # Метаданные последнего запроса — пишутся в историю exchange_rates.json
        self.last_meta: dict = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает курсы и возвращает их в стандартном формате."""

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        """GET-запрос с таймаутом, проверкой статуса и разбором JSON."""
        started = time.monotonic()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            raise ApiRequestError(
                f"превышено время ожидания ({self.config.REQUEST_TIMEOUT} с)"
            ) from None
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"сетевая ошибка ({error})") from None

        self.last_meta = {
            "request_ms": round((time.monotonic() - started) * MS_IN_SECOND),
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        if response.status_code != HTTP_OK:
            reason = STATUS_MESSAGES.get(
                response.status_code, f"код ответа {response.status_code}"
            )
            raise ApiRequestError(reason)
        try:
            return response.json()
        except ValueError:
            raise ApiRequestError("ответ не является JSON") from None


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют (BTC, ETH, SOL) к USD."""

    name = "CoinGecko"
    source_key = "coingecko"

    def fetch_rates(self) -> dict[str, float]:
        id_map = self.config.CRYPTO_ID_MAP
        codes = [code for code in self.config.CRYPTO_CURRENCIES if code in id_map]
        base = self.config.BASE_CURRENCY.lower()
        data = self._get_json(
            self.config.COINGECKO_URL,
            {"ids": ",".join(id_map[code] for code in codes), "vs_currencies": base},
        )
        rates = {}
        for code in codes:
            value = data.get(id_map[code], {}).get(base)
            if isinstance(value, (int, float)) and value > 0:
                rates[f"{code}_{self.config.BASE_CURRENCY}"] = float(value)
        if not rates:
            raise ApiRequestError("в ответе нет курсов")
        return rates

    def raw_id(self, code: str) -> str:
        """ID монеты в CoinGecko для истории."""
        return self.config.CRYPTO_ID_MAP.get(code, code.lower())


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют (EUR, GBP, RUB) к USD."""

    name = "ExchangeRate-API"
    source_key = "exchangerate"

    def fetch_rates(self) -> dict[str, float]:
        key = self.config.EXCHANGERATE_API_KEY
        if not key:
            raise ApiRequestError(
                "не задан API-ключ (переменная EXCHANGERATE_API_KEY или файл .env)"
            )
        base = self.config.BASE_CURRENCY
        data = self._get_json(f"{self.config.EXCHANGERATE_API_URL}/{key}/latest/{base}")
        if data.get("result") != "success":
            raise ApiRequestError(data.get("error-type", "неизвестная ошибка"))
        rates = {}
        for code in self.config.FIAT_CURRENCIES:
            value = (data.get("conversion_rates") or data.get("rates", {})).get(code)
            # API отдаёт «1 USD = N EUR», а нам нужно «1 EUR = M USD»
            if isinstance(value, (int, float)) and value > 0:
                rates[f"{code}_{base}"] = 1 / float(value)
        if not rates:
            raise ApiRequestError("в ответе нет курсов")
        return rates

    def raw_id(self, code: str) -> str:
        return code
