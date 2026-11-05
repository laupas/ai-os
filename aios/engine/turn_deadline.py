import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class TurnDeadline:
    """How long a turn may work. Time spent waiting for a human (an approval) does
    not count: while `waiting()` is held the clock stands still, so an approval may
    stay open as long as `approval.timeout_seconds` allows.
    """

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._timeout: asyncio.Timeout | None = None
        self._waiting = 0
        self._remaining = 0.0

    @asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        """The turn's work, cancelled with `TimeoutError` once its time is used up."""
        async with asyncio.timeout(self.seconds) as timeout:
            self._timeout = timeout
            try:
                yield
            finally:
                self._timeout = None

    @asynccontextmanager
    async def waiting(self) -> AsyncIterator[None]:
        """Stops the clock until the block ends. Parallel waits stop it once."""
        timeout = self._timeout
        if timeout is None:
            yield
            return
        loop = asyncio.get_running_loop()
        if self._waiting == 0:
            when = timeout.when()
            self._remaining = max(0.0, when - loop.time()) if when is not None else 0.0
            timeout.reschedule(None)
        self._waiting += 1
        try:
            yield
        finally:
            self._waiting -= 1
            if self._waiting == 0 and self._timeout is timeout:
                timeout.reschedule(loop.time() + self._remaining)
