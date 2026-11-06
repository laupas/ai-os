from signal_call import SignalCall


class SignalRule:
    """The v1 advisor's decision rule, now in code. A missing input simply does not
    fire its side of the rule."""

    def decide(self, rsi: float | None, fear_greed: int | None) -> SignalCall:
        cheap_rsi = rsi is not None and rsi < 30
        cheap_fg = fear_greed is not None and fear_greed < 30
        dear_rsi = rsi is not None and rsi > 70
        dear_fg = fear_greed is not None and fear_greed > 75
        if cheap_rsi and cheap_fg:
            return SignalCall.BUY
        if dear_rsi and dear_fg:
            return SignalCall.SELL
        if (rsi is not None and rsi < 40) or (fear_greed is not None and fear_greed < 35):
            return SignalCall.LEAN_BUY
        if (rsi is not None and rsi > 65) or (fear_greed is not None and fear_greed > 70):
            return SignalCall.LEAN_SELL
        return SignalCall.HOLD
