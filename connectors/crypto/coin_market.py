from pydantic import BaseModel


class CoinMarket(BaseModel):
    id: str
    symbol: str
    price_usd: float
    change_24h: float | None = None
    change_7d: float | None = None
    change_30d: float | None = None
