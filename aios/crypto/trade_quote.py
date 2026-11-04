from pydantic import BaseModel


class TradeQuote(BaseModel):
    coin: str
    pair: str
    side: str
    chf: float
    price_chf: float
    expected_volume: float
    est_fee_chf: float
    today_orders: int
    today_chf: float
    blocked_by: str | None = None
    """Why the limits would refuse this order, if they would."""
