from datetime import datetime, timedelta

from aios.common.clock import Clock


class LoginThrottle:
    """Slows down guessing: after `attempts` failed sign-ins for one name within
    `window`, that name is refused until the window has passed. Kept in memory,
    so a restart forgets it."""

    def __init__(
        self, clock: Clock, attempts: int = 5, window: timedelta = timedelta(minutes=15)
    ) -> None:
        self._clock = clock
        self._attempts = attempts
        self._window = window
        self._failures: dict[str, list[datetime]] = {}

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self._attempts

    def failed(self, key: str) -> None:
        self._failures[key.casefold()] = [*self._recent(key), self._clock.now()]

    def succeeded(self, key: str) -> None:
        self._failures.pop(key.casefold(), None)

    def _recent(self, key: str) -> list[datetime]:
        since = self._clock.now() - self._window
        return [t for t in self._failures.get(key.casefold(), []) if t > since]
