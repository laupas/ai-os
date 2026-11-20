import asyncio
from collections.abc import Callable

from aios.bootstrap.background_service import BackgroundService
from aios.config.live_app_config import LiveAppConfig


class AppConfigWatcher(BackgroundService):
    """Applies aios.yaml while ai-os runs: a save in the console, a commit made on
    the host, a branch switch. `read` gives the file as it counts (in the
    configuration repository: as committed), or None when there is none."""

    def __init__(
        self,
        config: LiveAppConfig,
        read: Callable[[], str | None],
        interval_seconds: float = 3,
    ) -> None:
        self._config = config
        self._read = read
        self._interval = interval_seconds
        self._last: str | None = None

    async def run(self) -> None:
        while True:
            await self.check()
            await asyncio.sleep(self._interval)

    async def check(self) -> None:
        text = await asyncio.to_thread(self._read)
        if text is None or text == self._last:
            return
        self._last = text
        self._config.apply(text)
