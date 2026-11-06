from coin_market import CoinMarket
from fear_greed import FearGreed
from pydantic import BaseModel
from signal_call import SignalCall


class CoinSignal(BaseModel):
    market: CoinMarket
    rsi_14: float | None
    fear_greed: FearGreed | None
    call: SignalCall
