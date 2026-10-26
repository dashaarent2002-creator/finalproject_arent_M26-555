"""Планировщик периодического обновления курсов."""

import threading

from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.updater import RatesUpdater, create_updater


class RatesScheduler:
    """Запускает RatesUpdater.run_update() раз в interval секунд."""

    def __init__(self, updater: RatesUpdater, interval_seconds: int):
        self.updater = updater
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()

    def run_forever(self) -> None:
        """Обновляет курсы до остановки (Ctrl+C или stop())."""
        while not self._stop_event.is_set():
            self.updater.run_update()
            self._stop_event.wait(self.interval_seconds)

    def stop(self) -> None:
        """Останавливает цикл обновления."""
        self._stop_event.set()


def main() -> None:
    """Точка входа: uv run parser-service — обновлять курсы по расписанию."""
    config = ParserConfig()
    scheduler = RatesScheduler(create_updater(config), config.UPDATE_INTERVAL_SECONDS)
    print(
        f"Parser Service запущен: обновление каждые "
        f"{config.UPDATE_INTERVAL_SECONDS} с. Остановка — Ctrl+C."
    )
    try:
        scheduler.run_forever()
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nParser Service остановлен.")


if __name__ == "__main__":
    main()
