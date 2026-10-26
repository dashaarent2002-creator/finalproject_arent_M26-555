"""Модели предметной области: User, Wallet, Portfolio."""

import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import (
    MIN_PASSWORD_LENGTH,
    format_amount,
    utc_now,
    validate_amount,
)

SALT_BYTES = 8
BALANCE_PRECISION = 8
BASE_CURRENCY = "USD"

# Заглушка курсов (1 единица валюты = N USD) — используется,
# если в get_total_value не передали курсы из кеша rates.json
STUB_EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 1.0786,
    "GBP": 1.2361,
    "RUB": 0.01016,
    "BTC": 59337.21,
    "ETH": 3720.0,
    "SOL": 145.12,
}


def hash_password(password: str, salt: str) -> str:
    """Односторонний хеш: sha256(password + salt)."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def validate_password(password: str) -> None:
    """Пароль должен быть строкой не короче 4 символов."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")


class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ):
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Создаёт нового пользователя: генерирует соль и хеширует пароль."""
        validate_password(password)
        salt = secrets.token_hex(SALT_BYTES)
        return cls(user_id, username, hash_password(password, salt), salt, utc_now())

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self) -> dict:
        """Информация о пользователе без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(timespec="seconds"),
        }

    def change_password(self, new_password: str) -> None:
        """Меняет пароль: новая соль + новый хеш."""
        validate_password(new_password)
        self._salt = secrets.token_hex(SALT_BYTES)
        self._hashed_password = hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли пароль с сохранённым хешем."""
        return hash_password(password, self._salt) == self._hashed_password

    def to_dict(self) -> dict:
        """Сериализация для users.json (дата — в формате ISO)."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(timespec="seconds"),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Восстановление пользователя из users.json."""
        return cls(
            data["user_id"],
            data["username"],
            data["hashed_password"],
            data["salt"],
            datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """Кошелёк пользователя для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = round(float(value), BALANCE_PRECISION)

    def deposit(self, amount: float) -> None:
        """Пополнение баланса на положительную сумму."""
        self.balance = self._balance + validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Снятие средств, если баланс позволяет."""
        value = validate_amount(amount)
        if value > self._balance:
            raise InsufficientFundsError(
                format_amount(self.currency_code, self._balance),
                format_amount(self.currency_code, value),
                self.currency_code,
            )
        self.balance = self._balance - value

    def get_balance_info(self) -> str:
        """Строка вида 'BTC: 0.0500'."""
        balance = format_amount(self.currency_code, self._balance)
        return f"{self.currency_code}: {balance}"

    def to_dict(self) -> dict:
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Все кошельки одного пользователя."""

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ):
        self._user_id = user_id
        self._wallets = dict(wallets) if wallets else {}
        self._user = user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def user(self) -> User | None:
        """Владелец портфеля (только чтение)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков — исходный словарь снаружи не изменить."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новый пустой кошелёк. Код валюты должен быть уникальным."""
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк '{currency_code}' уже есть в портфеле")
        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Кошелёк по коду валюты или None."""
        return self._wallets.get(currency_code)

    def get_total_value(
        self,
        base_currency: str = BASE_CURRENCY,
        exchange_rates: dict[str, float] | None = None,
    ) -> float:
        """Общая стоимость портфеля в базовой валюте.

        exchange_rates — курсы «1 единица валюты = N USD».
        Если не переданы, используется заглушка STUB_EXCHANGE_RATES.
        """
        rates = exchange_rates or STUB_EXCHANGE_RATES
        if base_currency not in rates:
            raise ValueError(f"Неизвестная базовая валюта '{base_currency}'")
        total_usd = 0.0
        for code, wallet in self._wallets.items():
            if code not in rates:
                raise ValueError(f"Нет курса для валюты '{code}'")
            total_usd += wallet.balance * rates[code]
        return total_usd / rates[base_currency]

    def to_dict(self) -> dict:
        """Сериализация для portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: wallet.to_dict() for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, user: User | None = None) -> "Portfolio":
        """Восстановление портфеля из portfolios.json."""
        wallets = {
            code: Wallet(code, info.get("balance", 0.0))
            for code, info in data.get("wallets", {}).items()
        }
        return cls(data["user_id"], wallets, user)
