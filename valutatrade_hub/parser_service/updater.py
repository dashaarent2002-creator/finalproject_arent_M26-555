"""RatesUpdater — координирует обновление курсов из всех источников."""

import logging

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import to_iso, utc_now
from valutatrade_hub.logging_config import PARSER_LOGGER, setup_logging
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = logging.getLogger(PARSER_LOGGER)


class RatesUpdater:
    """Опрашивает клиентов, объединяет курсы и сохраняет их."""

    def __init__(self, clients: list[BaseApiClient], storage: RatesStorage):
        self.clients = clients
        self.storage = storage

    def run_update(self, source: str | None = None) -> dict:
        """Запускает обновление.

        source — 'coingecko' или 'exchangerate'; None — все источники.
        Падение одного клиента не останавливает остальных.
        Возвращает сводку: updated, errors, last_refresh.
        """
        clients = self._select_clients(source)
        logger.info("Starting rates update...")
        timestamp = to_iso(utc_now())
        pairs, history, errors = {}, [], []

        for client in clients:
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                errors.append(str(error))
                logger.error("Failed to fetch from %s: %s", client.name, error.reason)
                continue
            logger.info("Fetching from %s... OK (%d rates)", client.name, len(rates))
            for key, rate in rates.items():
                pairs[key] = {
                    "rate": rate,
                    "updated_at": timestamp,
                    "source": client.name,
                }
                history.append(self._history_record(client, key, rate, timestamp))

        updated = 0
        if pairs:
            logger.info(
                "Writing %d rates to %s...", len(pairs), self.storage.rates_path
            )
            updated = self.storage.update_cache(pairs, timestamp)
            self.storage.append_history(history)
        logger.info(
            "Update finished: %d rates updated, %d errors", updated, len(errors)
        )
        return {"updated": updated, "errors": errors, "last_refresh": timestamp}

    def _select_clients(self, source: str | None) -> list[BaseApiClient]:
        if source is None:
            return self.clients
        selected = [c for c in self.clients if c.source_key == source.lower()]
        if not selected:
            names = ", ".join(c.source_key for c in self.clients)
            raise ValueError(f"Неизвестный источник '{source}'. Доступны: {names}")
        return selected

    @staticmethod
    def _history_record(
        client: BaseApiClient, key: str, rate: float, timestamp: str
    ) -> dict:
        """Запись истории с id вида BTC_USD_2025-10-10T12:00:00Z."""
        from_code, to_code = key.split("_")
        return {
            "id": f"{key}_{timestamp}",
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "timestamp": timestamp,
            "source": client.name,
            "meta": {"raw_id": client.raw_id(from_code), **client.last_meta},
        }


def create_updater(config: ParserConfig | None = None) -> RatesUpdater:
    """Собирает RatesUpdater со всеми клиентами и хранилищем."""
    setup_logging()
    config = config or ParserConfig()
    clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
    return RatesUpdater(clients, RatesStorage(config))
