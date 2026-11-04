class RsiCalculator:
    """Wilder's relative strength index over daily closes."""

    def __init__(self, period: int = 14) -> None:
        self._period = period

    def rsi(self, closes: list[float]) -> float | None:
        n = self._period
        if len(closes) <= n:
            return None
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0.0) for d in deltas]
        losses = [max(-d, 0.0) for d in deltas]
        avg_gain = sum(gains[:n]) / n
        avg_loss = sum(losses[:n]) / n
        for i in range(n, len(deltas)):
            avg_gain = (avg_gain * (n - 1) + gains[i]) / n
            avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        if avg_loss == 0:
            return 100.0
        return round(100 - 100 / (1 + avg_gain / avg_loss), 1)
