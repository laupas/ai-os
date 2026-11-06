from datetime import datetime

from pydantic import BaseModel
from trade_side import TradeSide


class Trade(BaseModel):
    """An executed spot order. The trading limits are counted from these."""

    id: str
    side: TradeSide
    coin: str
    pair: str
    chf_amount: float
    executed_volume: float
    executed_price: float
    executed_cost_chf: float
    fee_chf: float
    order_id: str
    executed_at: datetime
