"""Бизнес-логика: регистрация, вход, портфель, покупка/продажа, курсы."""

from valutatrade_hub.core.currencies import get_currency, is_crypto
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthError,
    CurrencyNotFoundError,
    RatesCacheError,
    RateUnavailableError,
    WalletNotFoundError,
)
from valutatrade_hub.core.models import BASE_CURRENCY, Portfolio, User
from valutatrade_hub.core.utils import (
    age_seconds,
    pair_key,
    to_iso,
    utc_now,
    validate_amount,
    validate_currency_code,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.updater import create_updater

# Синглтоны: единый доступ к настройкам и к JSON-хранилищу
settings = SettingsLoader()
db = DatabaseManager()

USERS = "users"
PORTFOLIOS = "portfolios"
RATES = "rates"
SOURCE_CRYPTO = "coingecko"
SOURCE_FIAT = "exchangerate"


# ---------- Пользователи ----------


def _load_users() -> list[User]:
    return [User.from_dict(item) for item in db.read(USERS, [])]


def _find_user(username: str) -> User | None:
    for user in _load_users():
        if user.username == username:
            return user
    return None


@log_action("REGISTER")
def register(username: str, password: str) -> dict:
    """Создаёт пользователя и пустой портфель."""
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    username = username.strip()
    users_data = db.read(USERS, [])
    if any(item["username"] == username for item in users_data):
        raise AuthError(f"Имя пользователя '{username}' уже занято")

    user_id = max((item["user_id"] for item in users_data), default=0) + 1
    user = User.create(user_id, username, password)
    db.write(USERS, users_data + [user.to_dict()])

    portfolios_data = db.read(PORTFOLIOS, [])
    portfolios_data.append(Portfolio(user_id).to_dict())
    db.write(PORTFOLIOS, portfolios_data)
    return {"user_id": user_id, "username": username}


@log_action("LOGIN")
def login(username: str, password: str) -> User:
    """Проверяет имя и пароль, возвращает пользователя."""
    user = _find_user(username)
    if user is None:
        raise AuthError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise AuthError("Неверный пароль")
    return user


def require_login(user: User | None) -> User:
    """Команды с портфелем доступны только после login."""
    if user is None:
        raise AuthError("Сначала выполните login")
    return user


# ---------- Портфели (чтение → изменение → запись) ----------


def load_portfolio(user_id: int) -> Portfolio:
    """Портфель пользователя из portfolios.json (пустой, если записи нет)."""
    user = next((u for u in _load_users() if u.user_id == user_id), None)
    for item in db.read(PORTFOLIOS, []):
        if item["user_id"] == user_id:
            return Portfolio.from_dict(item, user)
    return Portfolio(user_id, user=user)


def _save_portfolio(portfolio: Portfolio) -> None:
    portfolios_data = [
        item for item in db.read(PORTFOLIOS, []) if item["user_id"] != portfolio.user_id
    ]
    portfolios_data.append(portfolio.to_dict())
    db.write(PORTFOLIOS, portfolios_data)


# ---------- Курсы ----------


def _source_for(code: str) -> str:
    return SOURCE_CRYPTO if is_crypto(code) else SOURCE_FIAT


def _refresh(sources: set[str]) -> None:
    """Пытается обновить курсы через Parser Service."""
    updater = create_updater()
    for source in sorted(sources):
        updater.run_update(source)


def _usd_rates(codes: set[str]) -> tuple[dict[str, float], str, bool]:
    """Курсы «1 единица = N USD» для набора валют.

    Если курс отсутствует или старше TTL — пробует обновить кеш.
    Возвращает (курсы, самое старое время обновления, признак устаревания).
    """
    ttl = settings.get("rates_ttl_seconds")
    needed = {code for code in codes if code != BASE_CURRENCY}

    def collect() -> tuple[dict, list[str], set[str]]:
        pairs = db.read(RATES, {}).get("pairs", {})
        rates, times, stale = {BASE_CURRENCY: 1.0}, [], set()
        for code in needed:
            entry = pairs.get(pair_key(code, BASE_CURRENCY))
            if entry is None:
                continue
            rates[code] = entry["rate"]
            times.append(entry["updated_at"])
            if age_seconds(entry["updated_at"]) > ttl:
                stale.add(code)
        return rates, times, stale

    rates, times, stale = collect()
    missing = needed - set(rates)
    if missing or stale:
        try:
            _refresh({_source_for(code) for code in missing | stale})
        except ApiRequestError:
            pass
        rates, times, stale = collect()

    missing = needed - set(rates)
    if missing:
        code = sorted(missing)[0]
        raise RateUnavailableError(code, BASE_CURRENCY)
    updated_at = min(times) if times else to_iso(utc_now())
    return rates, updated_at, bool(stale)


def get_rate(from_code: str, to_code: str) -> dict:
    """Курс from→to через USD. Валюты проверяются через реестр."""
    from_code = get_currency(from_code).code
    to_code = get_currency(to_code).code
    try:
        rates, updated_at, stale = _usd_rates({from_code, to_code})
    except RateUnavailableError as error:
        raise RateUnavailableError(from_code, to_code, error.reason) from None
    rate = rates[from_code] / rates[to_code]
    return {
        "from": from_code,
        "to": to_code,
        "rate": rate,
        "reverse_rate": 1 / rate,
        "updated_at": updated_at,
        "stale": stale,
    }


def update_rates(source: str | None = None) -> dict:
    """Немедленное обновление курсов (команда update-rates)."""
    return create_updater().run_update(source)


def show_rates(
    currency: str | None = None, top: int | None = None, base: str | None = None
) -> dict:
    """Курсы из локального кеша с фильтрами --currency, --top, --base."""
    cache = db.read(RATES, {})
    pairs = cache.get("pairs", {}) if isinstance(cache, dict) else {}
    if not pairs:
        raise RatesCacheError(
            "Локальный кеш курсов пуст. Выполните 'update-rates', "
            "чтобы загрузить данные."
        )

    base_code = get_currency(base).code if base else BASE_CURRENCY
    rows = []
    if base_code != BASE_CURRENCY:
        base_entry = pairs.get(pair_key(base_code, BASE_CURRENCY))
        if base_entry is None:
            raise RatesCacheError(f"Курс для '{base_code}' не найден в кеше.")
        base_rate = base_entry["rate"]
        rows.append(_rate_row(BASE_CURRENCY, base_code, 1 / base_rate, base_entry))
    else:
        base_rate = 1.0

    for key, entry in pairs.items():
        from_code = key.split("_")[0]
        if from_code == base_code:
            continue
        rows.append(_rate_row(from_code, base_code, entry["rate"] / base_rate, entry))

    if currency:
        code = currency.strip().upper()
        rows = [row for row in rows if row["from"] == code]
        if not rows:
            raise RatesCacheError(f"Курс для '{code}' не найден в кеше.")
    if top is not None:
        if top <= 0:
            raise ValueError("'top' должен быть положительным целым числом")
        rows = [row for row in rows if _is_known_crypto(row["from"])]
        rows = sorted(rows, key=lambda row: row["rate"], reverse=True)[:top]
    else:
        rows = sorted(rows, key=lambda row: row["pair"])
    return {"rows": rows, "last_refresh": cache.get("last_refresh")}


def _rate_row(from_code: str, to_code: str, rate: float, entry: dict) -> dict:
    return {
        "pair": pair_key(from_code, to_code),
        "from": from_code,
        "rate": rate,
        "updated_at": entry["updated_at"],
        "source": entry.get("source", ""),
    }


def _is_known_crypto(code: str) -> bool:
    try:
        return is_crypto(code)
    except CurrencyNotFoundError:
        return False


# ---------- Портфель, покупка, продажа ----------


def show_portfolio(user_id: int, base: str = BASE_CURRENCY) -> dict:
    """Кошельки пользователя и их стоимость в базовой валюте."""
    try:
        base_code = get_currency(base).code
    except CurrencyNotFoundError:
        raise ValueError(f"Неизвестная базовая валюта '{base}'") from None
    portfolio = load_portfolio(user_id)
    wallets = portfolio.wallets
    if not wallets:
        return {"wallets": [], "total": 0.0, "base": base_code}

    rates, _, stale = _usd_rates(set(wallets) | {base_code})
    rows = [
        {
            "code": code,
            "balance": wallet.balance,
            "value": wallet.balance * rates[code] / rates[base_code],
        }
        for code, wallet in wallets.items()
    ]
    total = portfolio.get_total_value(base_code, rates)
    return {"wallets": rows, "total": total, "base": base_code, "stale": stale}


@log_action("BUY", verbose=True)
def buy(user_id: int, currency_code: str, amount: float) -> dict:
    """Покупка валюты за USD. Покупка USD — это пополнение счёта."""
    amount = validate_amount(amount)
    code = validate_currency_code(currency_code)
    portfolio = load_portfolio(user_id)

    rate = 1.0
    if code != BASE_CURRENCY:
        rate = get_rate(code, BASE_CURRENCY)["rate"]
        cost = amount * rate
        usd_wallet = portfolio.get_wallet(BASE_CURRENCY)
        if usd_wallet is None:
            usd_wallet = portfolio.add_currency(BASE_CURRENCY)
        usd_wallet.withdraw(cost)

    wallet = portfolio.get_wallet(code) or portfolio.add_currency(code)
    before = wallet.balance
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "base": BASE_CURRENCY,
        "before": before,
        "after": wallet.balance,
        "cost": amount * rate,
    }


@log_action("SELL", verbose=True)
def sell(user_id: int, currency_code: str, amount: float) -> dict:
    """Продажа валюты: выручка в USD зачисляется на USD-кошелёк."""
    amount = validate_amount(amount)
    code = validate_currency_code(currency_code)
    if code == BASE_CURRENCY:
        raise ValueError(
            f"{BASE_CURRENCY} — базовая валюта: её нельзя продать за {BASE_CURRENCY}"
        )
    portfolio = load_portfolio(user_id)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise WalletNotFoundError(code)

    rate = get_rate(code, BASE_CURRENCY)["rate"]
    before = wallet.balance
    wallet.withdraw(amount)
    revenue = amount * rate
    usd_wallet = portfolio.get_wallet(BASE_CURRENCY) or portfolio.add_currency(
        BASE_CURRENCY
    )
    usd_wallet.deposit(revenue)
    _save_portfolio(portfolio)
    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "base": BASE_CURRENCY,
        "before": before,
        "after": wallet.balance,
        "revenue": revenue,
    }
