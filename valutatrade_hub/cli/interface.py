"""Командный интерфейс ValutaTrade Hub.

CLI только разбирает команды, вызывает функции из core/usecases.py
и превращает результаты и исключения в понятные сообщения.
"""

import shlex

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import all_currencies
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    RateUnavailableError,
    ValutaTradeError,
)
from valutatrade_hub.core.models import BASE_CURRENCY, User
from valutatrade_hub.core.utils import (
    format_amount,
    format_money,
    format_rate,
    format_timestamp,
)
from valutatrade_hub.logging_config import setup_logging

PROMPT = "> "
SEPARATOR = "-" * 33
FLAG_PREFIX = "--"
EXIT_COMMANDS = ("exit", "quit")

# Описание команд: обязательные и необязательные аргументы, справка
COMMANDS = {
    "register": {
        "required": ("username", "password"),
        "optional": (),
        "usage": "register --username <имя> --password <пароль>",
        "help": "зарегистрироваться",
    },
    "login": {
        "required": ("username", "password"),
        "optional": (),
        "usage": "login --username <имя> --password <пароль>",
        "help": "войти в систему",
    },
    "logout": {
        "required": (),
        "optional": (),
        "usage": "logout",
        "help": "выйти из аккаунта",
    },
    "show-portfolio": {
        "required": (),
        "optional": ("base",),
        "usage": "show-portfolio [--base <валюта>]",
        "help": "показать кошельки и итоговую стоимость",
    },
    "buy": {
        "required": ("currency", "amount"),
        "optional": (),
        "usage": "buy --currency <код> --amount <количество>",
        "help": "купить валюту за USD (buy --currency USD — пополнить счёт)",
    },
    "sell": {
        "required": ("currency", "amount"),
        "optional": (),
        "usage": "sell --currency <код> --amount <количество>",
        "help": "продать валюту, выручка зачисляется в USD",
    },
    "get-rate": {
        "required": ("from", "to"),
        "optional": (),
        "usage": "get-rate --from <код> --to <код>",
        "help": "курс одной валюты к другой",
    },
    "update-rates": {
        "required": (),
        "optional": ("source",),
        "usage": "update-rates [--source coingecko|exchangerate]",
        "help": "обновить курсы из внешних API",
    },
    "show-rates": {
        "required": (),
        "optional": ("currency", "top", "base"),
        "usage": "show-rates [--currency <код>] [--top <N>] [--base <код>]",
        "help": "показать курсы из локального кеша",
    },
    "currencies": {
        "required": (),
        "optional": (),
        "usage": "currencies",
        "help": "список поддерживаемых валют",
    },
    "help": {
        "required": (),
        "optional": (),
        "usage": "help [<команда>]",
        "help": "справка",
    },
    "exit": {
        "required": (),
        "optional": (),
        "usage": "exit",
        "help": "выход из программы",
    },
}


def parse_flags(tokens: list[str]) -> dict[str, str]:
    """['--username', 'alice', '--password', '1234'] → {'username': 'alice', ...}."""
    flags = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith(FLAG_PREFIX) or len(token) == len(FLAG_PREFIX):
            raise ValueError(f"Некорректный аргумент: {token}")
        name = token[len(FLAG_PREFIX) :]
        if index + 1 >= len(tokens) or tokens[index + 1].startswith(FLAG_PREFIX):
            raise ValueError(f"Не указано значение для --{name}")
        flags[name] = tokens[index + 1]
        index += 2
    return flags


def check_flags(command: str, flags: dict[str, str]) -> None:
    """Проверяет обязательные и допустимые аргументы команды."""
    spec = COMMANDS[command]
    allowed = set(spec["required"]) | set(spec["optional"])
    for name in flags:
        if name not in allowed:
            raise ValueError(
                f"Неизвестный аргумент --{name}. Использование: {spec['usage']}"
            )
    for name in spec["required"]:
        if name not in flags:
            raise ValueError(f"Укажите --{name}. Использование: {spec['usage']}")


def print_currencies() -> None:
    """Таблица поддерживаемых валют."""
    table = PrettyTable(["Код", "Описание"])
    table.align = "l"
    for currency in all_currencies():
        table.add_row([currency.code, currency.get_display_info()])
    print(table)


class CommandLineInterface:
    """Главный цикл: читает команды и хранит текущую сессию."""

    def __init__(self):
        self.current_user: User | None = None
        self.handlers = {
            "register": self.cmd_register,
            "login": self.cmd_login,
            "logout": self.cmd_logout,
            "show-portfolio": self.cmd_show_portfolio,
            "buy": self.cmd_buy,
            "sell": self.cmd_sell,
            "get-rate": self.cmd_get_rate,
            "update-rates": self.cmd_update_rates,
            "show-rates": self.cmd_show_rates,
            "currencies": self.cmd_currencies,
        }

    def run(self) -> None:
        """Запускает интерактивный режим."""
        setup_logging()
        print("***ValutaTrade Hub***")
        print("Введите 'help' для списка команд, 'exit' для выхода.")
        while True:
            try:
                line = input(PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.split()[0] in EXIT_COMMANDS:
                print("До свидания!")
                break
            self.execute(line)

    def execute(self, line: str) -> None:
        """Выполняет одну команду и печатает понятное сообщение об ошибке."""
        try:
            tokens = shlex.split(line)
        except ValueError:
            print(f"Некорректная команда: {line}")
            return
        command, args = tokens[0], tokens[1:]

        if command == "help":
            self.cmd_help(args)
            return
        if command not in self.handlers:
            print(f"Неизвестная команда '{command}'. Введите 'help'.")
            return
        try:
            flags = parse_flags(args)
            check_flags(command, flags)
            self.handlers[command](flags)
        except InsufficientFundsError as error:
            print(error)
        except CurrencyNotFoundError as error:
            print(error)
            print("Поддерживаемые валюты:")
            print_currencies()
            print("Справка: help get-rate")
        except RateUnavailableError as error:
            if command == "get-rate":
                print(
                    f"Курс {error.from_code}→{error.to_code} недоступен. "
                    "Повторите попытку позже."
                )
            else:
                print(error)
                print("Повторите попытку позже или выполните update-rates.")
        except ApiRequestError as error:
            print(error)
            print("Повторите попытку позже или проверьте подключение к сети.")
        except (ValutaTradeError, ValueError) as error:
            print(error)
        except Exception as error:  # последний рубеж: программа не падает
            print(f"Произошла непредвиденная ошибка: {error}")

    # ---------- Команды ----------

    def cmd_help(self, args: list[str]) -> None:
        if args:
            spec = COMMANDS.get(args[0])
            if spec is None:
                print(f"Неизвестная команда '{args[0]}'.")
                return
            print(f"{args[0]} — {spec['help']}")
            print(f"Использование: {spec['usage']}")
            return
        print("Команды:")
        for spec in COMMANDS.values():
            print(f"  {spec['usage']:<58} {spec['help']}")

    def cmd_register(self, flags: dict) -> None:
        result = usecases.register(flags["username"], flags["password"])
        print(
            f"Пользователь '{result['username']}' зарегистрирован "
            f"(id={result['user_id']}). "
            f"Войдите: login --username {result['username']} --password ****"
        )

    def cmd_login(self, flags: dict) -> None:
        self.current_user = usecases.login(flags["username"], flags["password"])
        print(f"Вы вошли как '{self.current_user.username}'")

    def cmd_logout(self, flags: dict) -> None:
        user = usecases.require_login(self.current_user)
        self.current_user = None
        print(f"Вы вышли из аккаунта '{user.username}'")

    def cmd_show_portfolio(self, flags: dict) -> None:
        user = usecases.require_login(self.current_user)
        base = flags.get("base", BASE_CURRENCY).upper()
        result = usecases.show_portfolio(user.user_id, base)
        if not result["wallets"]:
            print(f"Портфель пользователя '{user.username}' пуст.")
            print("Пополните счёт: buy --currency USD --amount 1000")
            return
        print(f"Портфель пользователя '{user.username}' (база: {result['base']}):")
        for row in result["wallets"]:
            print(
                f"- {row['code']}: {format_amount(row['code'], row['balance'])} "
                f"→ {row['value']:.2f} {result['base']}"
            )
        print(SEPARATOR)
        print(f"ИТОГО: {format_money(result['total'])} {result['base']}")
        if result.get("stale"):
            print("Внимание: часть курсов устарела. Выполните update-rates.")

    def cmd_buy(self, flags: dict) -> None:
        user = usecases.require_login(self.current_user)
        result = usecases.buy(user.user_id, flags["currency"].upper(), flags["amount"])
        code = result["currency"]
        if code == BASE_CURRENCY:
            print(f"Счёт пополнен: {format_amount(code, result['amount'])} {code}")
        else:
            print(
                f"Покупка выполнена: {format_amount(code, result['amount'])} {code} "
                f"по курсу {format_rate(result['rate'])} {BASE_CURRENCY}/{code}"
            )
        self._print_change(code, result)
        if code != BASE_CURRENCY:
            print(
                f"Оценочная стоимость покупки: {format_money(result['cost'])} "
                f"{BASE_CURRENCY}"
            )

    def cmd_sell(self, flags: dict) -> None:
        user = usecases.require_login(self.current_user)
        result = usecases.sell(user.user_id, flags["currency"].upper(), flags["amount"])
        code = result["currency"]
        print(
            f"Продажа выполнена: {format_amount(code, result['amount'])} {code} "
            f"по курсу {format_rate(result['rate'])} {BASE_CURRENCY}/{code}"
        )
        self._print_change(code, result)
        print(f"Оценочная выручка: {format_money(result['revenue'])} {BASE_CURRENCY}")

    def cmd_get_rate(self, flags: dict) -> None:
        result = usecases.get_rate(flags["from"].upper(), flags["to"].upper())
        print(
            f"Курс {result['from']}→{result['to']}: {format_rate(result['rate'])} "
            f"(обновлено: {format_timestamp(result['updated_at'])})"
        )
        print(
            f"Обратный курс {result['to']}→{result['from']}: "
            f"{format_rate(result['reverse_rate'])}"
        )
        if result["stale"]:
            print("Внимание: курс устарел, обновить не удалось.")
            print("Выполните update-rates.")

    def cmd_update_rates(self, flags: dict) -> None:
        result = usecases.update_rates(flags.get("source"))
        if result["errors"]:
            print("Update completed with errors. Check logs/parser.log for details.")
        else:
            print(
                f"Update successful. Total rates updated: {result['updated']}. "
                f"Last refresh: {result['last_refresh']}"
            )

    def cmd_show_rates(self, flags: dict) -> None:
        top = None
        if "top" in flags:
            try:
                top = int(flags["top"])
            except ValueError:
                raise ValueError(
                    "'top' должен быть положительным целым числом"
                ) from None
        result = usecases.show_rates(
            flags.get("currency"), top, flags.get("base", "").upper() or None
        )
        print(f"Rates from cache (updated at {result['last_refresh']}):")
        table = PrettyTable(["Пара", "Курс", "Обновлено", "Источник"])
        table.align["Пара"] = "l"
        table.align["Курс"] = "r"
        for row in result["rows"]:
            table.add_row(
                [
                    row["pair"],
                    format_rate(row["rate"]),
                    format_timestamp(row["updated_at"]),
                    row["source"],
                ]
            )
        print(table)

    def cmd_currencies(self, flags: dict) -> None:
        print_currencies()

    @staticmethod
    def _print_change(code: str, result: dict) -> None:
        print("Изменения в портфеле:")
        print(
            f"- {code}: было {format_amount(code, result['before'])} "
            f"→ стало {format_amount(code, result['after'])}"
        )


def main() -> None:
    """Точка входа консольного приложения."""
    CommandLineInterface().run()
