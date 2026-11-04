from pydantic import BaseModel

from aios.crypto.coin_market import CoinMarket
from aios.crypto.fear_greed import FearGreed
from aios.crypto.signal_call import SignalCall


class CoinSignal(BaseModel):
    market: CoinMarket
    rsi_14: float | None
    fear_greed: FearGreed | None
    call: SignalCall
