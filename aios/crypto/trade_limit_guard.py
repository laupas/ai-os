from zoneinfo import ZoneInfo

from aios.common.clock import Clock
from aios.crypto.trade_limits import TradeLimits
from aios.entities.trades.trade import Trade
from aios.storage.collection import Collection


class TradeLimitGuard:
    """Says why an order may not be placed, or None when it may.

    The trading day is the local day in `timezone`, so "500 CHF a day" means the
    user's day rather than UTC's.
    """

    def __init__(
        self, limits: TradeLimits, trades: Collection[Trade], clock: Clock, timezone: str
    ) -> None:
        self._limits = limits
        self._trades = trades
        self._clock = clock
        self._zone = ZoneInfo(timezone)

    def check_order(self, side: str, coin: str, chf: float) -> str | None:
        limits = self._limits
        if side not in ("buy", "sell"):
            return f"side must be buy or sell, not {side!r}"
        if coin not in limits.pairs:
            return f"{coin} is not tradable (allowed: {', '.join(limits.pairs)})"
        if chf < limits.min_chf:
            return f"{chf} CHF is below the minimum of {limits.min_chf} CHF"
        if chf > limits.max_chf_per_order:
            return f"{chf} CHF is above the per-order cap of {limits.max_chf_per_order} CHF"
        today = self.trades_today()
        if len(today) >= limits.max_orders_per_day:
            return f"daily cap of {limits.max_orders_per_day} orders reached"
        spent = sum(t.chf_amount for t in today)
        if spent + chf > limits.max_chf_per_day:
            return f"would exceed the daily {limits.max_chf_per_day} CHF cap ({spent:.2f} used)"
        latest = max((t.executed_at for t in self._trades.all()), default=None)
        if latest is not None:
            age = (self._clock.now() - latest).total_seconds()
            if age < limits.cooldown_seconds:
                return f"cooldown: {limits.cooldown_seconds - age:.0f}s left"
        return None

    def trades_today(self) -> list[Trade]:
        today = self._clock.now().astimezone(self._zone).date()
        return self._trades.filter(lambda t: t.executed_at.astimezone(self._zone).date() == today)
