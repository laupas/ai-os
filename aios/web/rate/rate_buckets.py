import time
from collections.abc import Callable

LIMIT = 50_000
"""Keys kept at most; the fullest (least used) are dropped first."""


class RateBuckets:
    """Token buckets in memory: each key may make `per_minute` requests a minute,
    in bursts up to that many. `take` answers how many seconds to wait, 0 when the
    request may go ahead."""

    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._buckets: dict[str, tuple[float, float]] = {}

    def take(self, key: str, per_minute: int) -> float:
        now = self._now()
        tokens, then = self._buckets.get(key, (float(per_minute), now))
        tokens = min(float(per_minute), tokens + (now - then) * per_minute / 60)
        if tokens < 1:
            self._buckets[key] = (tokens, now)
            return (1 - tokens) * 60 / per_minute
        self._buckets[key] = (tokens - 1, now)
        if len(self._buckets) > LIMIT:
            self._forget_some()
        return 0.0

    def _forget_some(self) -> None:
        fullest = sorted(self._buckets, key=lambda k: self._buckets[k][0], reverse=True)
        for key in fullest[: LIMIT // 10]:
            del self._buckets[key]
