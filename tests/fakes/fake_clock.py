from datetime import UTC, datetime, timedelta

from aios.common.clock import Clock


class FakeClock(Clock):
    """Advances one second per call, so ordering by time is deterministic."""

    def __init__(self) -> None:
        self._now = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now
