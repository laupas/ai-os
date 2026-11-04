from enum import StrEnum


class SignalCall(StrEnum):
    BUY = "BUY"
    LEAN_BUY = "LEAN BUY"
    HOLD = "HOLD"
    LEAN_SELL = "LEAN SELL"
    SELL = "SELL"
