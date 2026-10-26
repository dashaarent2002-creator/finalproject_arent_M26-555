"""Иерархия валют: абстрактный Currency и наследники Fiat/Crypto."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

CODE_MIN_LENGTH = 2
CODE_MAX_LENGTH = 5


class Currency(ABC):
    """Базовая валюта: человекочитаемое имя и код (тикер)."""

    def __init__(self, name: str, code: str):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if not is_valid_code_format(code):
            raise ValueError(
                f"Код валюты '{code}' должен быть в верхнем регистре, "
                f"{CODE_MIN_LENGTH}–{CODE_MAX_LENGTH} символов, без пробелов"
            )
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для интерфейса и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта (выпускается государством или зоной)."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и рыночной капитализацией."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {short_number(self.market_cap)})"
        )


def short_number(value: float) -> str:
    """Краткая запись большого числа: 1120000000000 → '1.12e12'."""
    return f"{value:.2e}".replace("e+", "e")


def is_valid_code_format(code: str) -> bool:
    """Проверяет формат кода: верхний регистр, 2–5 символов, без пробелов."""
    return (
        isinstance(code, str)
        and CODE_MIN_LENGTH <= len(code) <= CODE_MAX_LENGTH
        and code.isalnum()
        and code == code.upper()
    )


# Реестр поддерживаемых валют
_REGISTRY: dict[str, Currency] = {
    currency.code: currency
    for currency in (
        FiatCurrency("US Dollar", "USD", "United States"),
        FiatCurrency("Euro", "EUR", "Eurozone"),
        FiatCurrency("British Pound", "GBP", "United Kingdom"),
        FiatCurrency("Russian Ruble", "RUB", "Russia"),
        CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
        CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
        CryptoCurrency("Solana", "SOL", "Proof of History", 7.1e10),
    )
}


def get_currency(code: str) -> Currency:
    """Возвращает валюту по коду. Неизвестный код → CurrencyNotFoundError."""
    normalized = code.strip().upper() if isinstance(code, str) else ""
    if normalized not in _REGISTRY:
        raise CurrencyNotFoundError(code)
    return _REGISTRY[normalized]


def supported_codes() -> list[str]:
    """Список кодов всех поддерживаемых валют."""
    return list(_REGISTRY)


def all_currencies() -> list[Currency]:
    """Все валюты реестра."""
    return list(_REGISTRY.values())


def is_crypto(code: str) -> bool:
    """True, если валюта — криптовалюта."""
    return isinstance(get_currency(code), CryptoCurrency)
