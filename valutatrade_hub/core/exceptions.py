"""Пользовательские исключения ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовое исключение приложения."""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке (Wallet.withdraw, usecases.buy/sell)."""

    def __init__(self, available: str, required: str, code: str):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available} {code}, "
            f"требуется {required} {code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    """Неизвестная валюта (currencies.get_currency, валидация в get-rate)."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutaTradeError):
    """Сбой внешнего API (слой получения курсов / Parser Service)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class RateUnavailableError(ValutaTradeError):
    """Курса нет в кеше, и обновить его не удалось."""

    def __init__(self, from_code: str, to_code: str, reason: str = ""):
        self.from_code = from_code
        self.to_code = to_code
        self.reason = reason
        super().__init__(f"Не удалось получить курс для {from_code}→{to_code}")


class AuthError(ValutaTradeError):
    """Ошибки регистрации, входа и доступа без логина."""


class WalletNotFoundError(ValutaTradeError):
    """У пользователя нет кошелька в указанной валюте."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )


class RatesCacheError(ValutaTradeError):
    """Кеш курсов пуст или нужного курса в нём нет."""
