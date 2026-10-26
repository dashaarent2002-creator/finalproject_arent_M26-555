"""Декоратор @log_action — логирование доменных операций."""

import functools
import inspect
import logging

from valutatrade_hub.logging_config import ACTIONS_LOGGER

logger = logging.getLogger(ACTIONS_LOGGER)

# Аргументы функции, которые попадают в лог
LOGGED_ARGS = ("user_id", "username", "currency_code", "amount")
# Поля из результата функции, которые попадают в лог
LOGGED_RESULT_FIELDS = ("rate", "base")


def _format_value(value, numeric: bool = False) -> str:
    """Дробные числа — с 4 знаками, строки — в кавычках.

    numeric=True — значение-строку (например, amount из CLI) пробуем как число.
    """
    if numeric and isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass
    if isinstance(value, str):
        return f"'{value}'"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def log_action(action: str, verbose: bool = False):
    """Логирует вызов операции на уровне INFO.

    action  — имя операции (BUY, SELL, REGISTER, LOGIN).
    verbose — добавить в лог состояние кошелька «было → стало».
    Исключения не глотаются: они записываются в лог и пробрасываются дальше.
    """

    def decorator(func):
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            parts = [action]
            for name in LOGGED_ARGS:
                if name in bound.arguments:
                    label = "currency" if name == "currency_code" else name
                    value = _format_value(
                        bound.arguments[name], numeric=name == "amount"
                    )
                    parts.append(f"{label}={value}")
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                parts.append("result=ERROR")
                parts.append(f"error_type={type(error).__name__}")
                parts.append(f"error_message='{error}'")
                logger.info(" ".join(parts))
                raise
            if isinstance(result, dict):
                for name in LOGGED_RESULT_FIELDS:
                    if result.get(name) is not None:
                        parts.append(f"{name}={_format_value(result[name])}")
                if verbose and "before" in result:
                    parts.append(
                        f"wallet={_format_value(result['before'])}"
                        f"→{_format_value(result['after'])}"
                    )
            parts.append("result=OK")
            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
