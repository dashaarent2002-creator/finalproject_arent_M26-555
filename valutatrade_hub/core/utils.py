"""Вспомогательные функции: валидация, время, форматирование."""

from datetime import datetime, timezone

from valutatrade_hub.core.currencies import get_currency, is_crypto

MIN_PASSWORD_LENGTH = 4
CRYPTO_DECIMALS = 4
FIAT_DECIMALS = 2
SMALL_RATE_DECIMALS = 8
MEDIUM_RATE_DECIMALS = 4
LARGE_RATE = 100
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
AMOUNT_ERROR = "'amount' должен быть положительным числом"


def validate_amount(amount) -> float:
    """Проверяет, что amount — положительное число, и возвращает float."""
    if isinstance(amount, bool):
        raise ValueError(AMOUNT_ERROR)
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValueError(AMOUNT_ERROR) from None
    if value <= 0 or value != value or value == float("inf"):
        raise ValueError(AMOUNT_ERROR)
    return value


def validate_currency_code(code) -> str:
    """Проверяет код валюты через реестр и возвращает его в верхнем регистре."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return get_currency(code.strip().upper()).code


def utc_now() -> datetime:
    """Текущее время в UTC."""
    return datetime.now(timezone.utc)


def to_iso(moment: datetime) -> str:
    """datetime → строка ISO-UTC вида 2025-10-10T12:00:00Z."""
    return moment.astimezone(timezone.utc).strftime(ISO_UTC_FORMAT)


def parse_iso(text: str) -> datetime:
    """Строка ISO → datetime с часовым поясом UTC."""
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def age_seconds(text: str) -> float:
    """Сколько секунд прошло с момента, записанного в строке ISO."""
    return (utc_now() - parse_iso(text)).total_seconds()


def format_timestamp(text: str) -> str:
    """'2025-10-09T00:03:22Z' → '2025-10-09 00:03:22'."""
    return parse_iso(text).strftime("%Y-%m-%d %H:%M:%S")


def format_amount(code: str, value: float) -> str:
    """Количество валюты: 4 знака для криптовалют, 2 — для фиата."""
    decimals = CRYPTO_DECIMALS if is_crypto(code) else FIAT_DECIMALS
    return f"{value:.{decimals}f}"


def format_money(value: float) -> str:
    """Денежная сумма с разделителем тысяч: 3329 → '3,329.00'."""
    return f"{value:,.2f}"


def format_rate(rate: float) -> str:
    """Курс: 59337.21 → '59337.21', 1.0786 → '1.0786', 0.00001685 → '0.00001685'."""
    if rate >= LARGE_RATE:
        return f"{rate:.2f}"
    if rate >= 1:
        return f"{rate:.{MEDIUM_RATE_DECIMALS}f}"
    return f"{rate:.{SMALL_RATE_DECIMALS}f}".rstrip("0").rstrip(".")


def pair_key(from_code: str, to_code: str) -> str:
    """Ключ пары валют: ('BTC', 'USD') → 'BTC_USD'."""
    return f"{from_code}_{to_code}"
