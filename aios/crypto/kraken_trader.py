import asyncio

from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.crypto.kraken_client import KrakenClient
from aios.crypto.kraken_error import KrakenError
from aios.crypto.trade_limit_guard import TradeLimitGuard
from aios.crypto.trade_limits import TradeLimits
from aios.crypto.trade_quote import TradeQuote
from aios.entities.trades.trade import Trade
from aios.entities.trades.trade_side import TradeSide
from aios.storage.collection import Collection

FILL_POLL_SECONDS = 2.0


class KrakenTrader:
    """Market orders on Kraken spot, always inside `TradeLimits`.

    The limits are checked again right before every order, whatever was checked
    when the order was proposed or approved.
    """

    def __init__(
        self,
        client: KrakenClient,
        guard: TradeLimitGuard,
        limits: TradeLimits,
        trades: Collection[Trade],
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._client = client
        self._guard = guard
        self._limits = limits
        self._trades = trades
        self._clock = clock
        self._ids = ids

    async def quote(self, side: str, coin: str, chf: float) -> TradeQuote:
        coin = coin.upper()
        pair = self._limits.pairs.get(coin, "")
        price = await self._price(pair, side) if pair else 0.0
        today = self._guard.trades_today()
        return TradeQuote(
            coin=coin,
            pair=pair,
            side=side,
            chf=chf,
            price_chf=price,
            expected_volume=round(chf / price, 8) if price else 0.0,
            est_fee_chf=round(chf * self._limits.taker_fee_rate, 4),
            today_orders=len(today),
            today_chf=round(sum(t.chf_amount for t in today), 2),
            blocked_by=self._guard.check_order(side, coin, chf),
        )

    async def execute(self, side: str, coin: str, chf: float) -> Trade:
        coin = coin.upper()
        reason = self._guard.check_order(side, coin, chf)
        if reason:
            raise KrakenError(f"refused by the limits: {reason}")
        pair = self._limits.pairs[coin]
        price = await self._price(pair, side)
        volume = round(chf / price, 8)
        added = await self._client.private(
            "/0/private/AddOrder",
            {"pair": pair, "type": side, "ordertype": "market", "volume": f"{volume:.8f}"},
        )
        txids = added.get("txid") or []
        if not txids:
            raise KrakenError("Kraken returned no order id")
        await asyncio.sleep(FILL_POLL_SECONDS)
        fill = (await self._client.private("/0/private/QueryOrders", {"txid": txids[0]})).get(
            txids[0], {}
        )
        executed_volume = float(fill.get("vol_exec") or volume)
        executed_cost = float(fill.get("cost") or chf)
        return await self._trades.put(
            Trade(
                id=self._ids.new_id(),
                side=TradeSide(side),
                coin=coin,
                pair=pair,
                chf_amount=chf,
                executed_volume=executed_volume,
                executed_price=executed_cost / executed_volume if executed_volume else price,
                executed_cost_chf=executed_cost,
                fee_chf=float(fill.get("fee") or chf * self._limits.taker_fee_rate),
                order_id=txids[0],
                executed_at=self._clock.now(),
            )
        )

    async def balance(self) -> dict[str, float]:
        balances = await self._client.private("/0/private/Balance", {})
        wanted = {
            "ZCHF": "CHF",
            "CHF": "CHF",
            "XXBT": "BTC",
            "XBT": "BTC",
            "XETH": "ETH",
            "ETH": "ETH",
        }
        return {wanted[k]: float(v) for k, v in balances.items() if k in wanted}

    async def _price(self, pair: str, side: str) -> float:
        ticker = await self._client.public("/0/public/Ticker", {"pair": pair})
        data = next(iter(ticker.values()))
        return float(data["a" if side == "buy" else "b"][0])
