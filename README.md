# ValutaTrade Hub

Консольная платформа для симуляции торговли валютами. Пользователь регистрируется,
пополняет виртуальный счёт в USD, покупает и продаёт фиатные валюты и криптовалюты
и следит за актуальными курсами.

Система состоит из двух частей:

- **Core Service** — интерфейс командной строки, пользователи, кошельки, покупка и продажа;
- **Parser Service** — получает курсы из внешних API (CoinGecko и ExchangeRate-API)
  и сохраняет их в локальный кеш и историю.

Проект написан в объектно-ориентированном стиле: классы `User`, `Wallet`, `Portfolio`,
иерархия валют `Currency → FiatCurrency / CryptoCurrency`, синглтоны `SettingsLoader`
и `DatabaseManager`, API-клиенты с общим базовым классом `BaseApiClient`.

## Демо

[![asciicast](https://asciinema.org/a/GSTMPWz2fmpohZOI.svg)](https://asciinema.org/a/GSTMPWz2fmpohZOI)

## Установка

Нужен [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # или: make install
```

Сборка и установка пакета:

```bash
uv build                         # или: make build
uvx twine check dist/*           # или: make publish (проверка без публикации)
uv tool install dist/*.whl       # или: make package-install
```

## Запуск

```bash
uv run project       # или: make project, или: python main.py
```

После установки пакета через `uv tool install` достаточно набрать `project`.

## Команды

| Команда | Что делает |
|---|---|
| `register --username <имя> --password <пароль>` | регистрация (пароль от 4 символов) |
| `login --username <имя> --password <пароль>` | вход в систему |
| `logout` | выход из аккаунта |
| `show-portfolio [--base <код>]` | кошельки и итоговая стоимость (по умолчанию в USD) |
| `buy --currency <код> --amount <кол-во>` | покупка валюты за USD; `buy --currency USD` — пополнение счёта |
| `sell --currency <код> --amount <кол-во>` | продажа валюты, выручка зачисляется в USD |
| `get-rate --from <код> --to <код>` | курс одной валюты к другой |
| `update-rates [--source coingecko\|exchangerate]` | обновить курсы из внешних API |
| `show-rates [--currency <код>] [--top <N>] [--base <код>]` | курсы из локального кеша |
| `currencies` | список поддерживаемых валют |
| `help [<команда>]` | справка |
| `exit` | выход |

Поддерживаемые валюты: USD, EUR, GBP, RUB (фиат) и BTC, ETH, SOL (крипто).

### Пример сессии

```
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****
> login --username alice --password 1234
Вы вошли как 'alice'
> buy --currency USD --amount 5000
Счёт пополнен: 5000.00 USD
Изменения в портфеле:
- USD: было 0.00 → стало 5000.00
> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 59337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
Оценочная стоимость покупки: 2,966.86 USD
> sell --currency BTC --amount 0.01
Продажа выполнена: 0.0100 BTC по курсу 59337.21 USD/BTC
Изменения в портфеле:
- BTC: было 0.0500 → стало 0.0400
Оценочная выручка: 593.37 USD
> show-portfolio
Портфель пользователя 'alice' (база: USD):
- USD: 2626.51 → 2626.51 USD
- BTC: 0.0400 → 2373.49 USD
---------------------------------
ИТОГО: 5,000.00 USD
> get-rate --from USD --to BTC
Курс USD→BTC: 0.00001685 (обновлено: 2025-10-10 12:00:00)
Обратный курс BTC→USD: 59337.21
> sell --currency BTC --amount 1
Недостаточно средств: доступно 0.0400 BTC, требуется 1.0000 BTC
```

### Логика покупки и продажи

- При покупке криптовалюты или EUR/GBP/RUB стоимость `amount × курс` списывается
  с USD-кошелька. Если долларов не хватает — `InsufficientFundsError`.
- При продаже выручка зачисляется на USD-кошелёк.
- Кошелёк для новой валюты создаётся автоматически при первой покупке.

## Курсы, кеш и TTL

- `data/rates.json` — локальный кеш: последний курс каждой пары к USD
  (`BTC_USD`, `EUR_USD`, …), время обновления и источник. Core читает только его.
- `data/exchange_rates.json` — история всех замеров Parser Service
  (id вида `BTC_USD_2025-10-10T12:00:00Z`, без дублей).
- Срок годности кеша — `rates_ttl_seconds` (по умолчанию 300 секунд) в секции
  `[tool.valutatrade]` файла `pyproject.toml`.
- Если курс старше TTL, `get-rate`, `buy`, `sell` и `show-portfolio` пытаются обновить
  его через Parser Service. Если обновить не удалось, используется последнее значение
  с предупреждением «курс устарел». Если курса нет совсем — сообщение
  «Курс X→Y недоступен. Повторите попытку позже.»
- Запись файлов атомарная: сначала временный файл, затем переименование.

## Parser Service

- **CoinGecko** — курсы BTC, ETH, SOL (ключ не нужен).
- **ExchangeRate-API** — курсы EUR, GBP, RUB (нужен бесплатный ключ).

### Где хранить API-ключ

1. Зарегистрируйтесь на <https://www.exchangerate-api.com/> и скопируйте ключ.
2. Создайте в корне проекта файл `.env` (он в `.gitignore`, в репозиторий не попадает):

   ```bash
   cp .env.example .env
   ```

   и впишите ключ: `EXCHANGERATE_API_KEY=ваш_ключ`.
   Вместо файла можно задать переменную окружения `EXCHANGERATE_API_KEY`.

Без ключа приложение продолжает работать: криптовалюты обновляются из CoinGecko,
а для фиатных валют используется последнее значение из кеша.

### Запуск обновления

```bash
# Вручную из приложения
> update-rates
INFO: Starting rates update...
INFO: Fetching from CoinGecko... OK (3 rates)
INFO: Fetching from ExchangeRate-API... OK (3 rates)
INFO: Writing 6 rates to data/rates.json...
Update successful. Total rates updated: 6. Last refresh: 2025-10-10T15:30:00Z

# По расписанию (каждые 5 минут, остановка — Ctrl+C)
uv run parser-service
```

## Логи и ошибки

- `logs/actions.log` — операции пользователей (декоратор `@log_action` на
  `register`, `login`, `buy`, `sell`), ротация по размеру (1 МБ, 5 файлов):

  ```
  INFO 2025-10-09T12:05:22 BUY user_id=1 currency='BTC' amount=0.0500 rate=59337.2100 base='USD' wallet=0.0000→0.0500 result=OK
  ```

- `logs/parser.log` — ход обновления курсов.
- Исключения ядра (`InsufficientFundsError`, `CurrencyNotFoundError`, `ApiRequestError`
  и др.) пробрасываются в CLI и выводятся понятными сообщениями.

## Структура проекта

```
├── data/
│   ├── users.json            # пользователи
│   ├── portfolios.json       # портфели и кошельки
│   ├── rates.json            # кеш курсов для Core Service
│   └── exchange_rates.json   # история курсов Parser Service
├── valutatrade_hub/
│   ├── logging_config.py     # настройка логов и ротации
│   ├── decorators.py         # @log_action
│   ├── core/
│   │   ├── currencies.py     # Currency, FiatCurrency, CryptoCurrency, get_currency()
│   │   ├── exceptions.py     # пользовательские исключения
│   │   ├── models.py         # User, Wallet, Portfolio
│   │   ├── usecases.py       # бизнес-логика
│   │   └── utils.py          # валидация и форматирование
│   ├── infra/
│   │   ├── settings.py       # SettingsLoader (Singleton)
│   │   └── database.py       # DatabaseManager (Singleton)
│   ├── parser_service/
│   │   ├── config.py         # ParserConfig
│   │   ├── api_clients.py    # BaseApiClient, CoinGeckoClient, ExchangeRateApiClient
│   │   ├── updater.py        # RatesUpdater
│   │   ├── storage.py        # запись rates.json и exchange_rates.json
│   │   └── scheduler.py      # периодическое обновление
│   └── cli/
│       └── interface.py      # команды
├── main.py
├── pyproject.toml
├── Makefile
└── README.md
```

## Проверка стиля

```bash
uv run ruff check .   # или: make lint
```
