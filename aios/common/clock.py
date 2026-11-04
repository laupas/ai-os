from datetime import UTC, datetime


class Clock:
    """Source of the current time, injected so tests can control it."""

    def now(self) -> datetime:
        return datetime.now(UTC)
