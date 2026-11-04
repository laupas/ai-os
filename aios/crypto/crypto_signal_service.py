import logging

from aios.crypto.coin_gecko_client import CoinGeckoClient
from aios.crypto.coin_signal import CoinSignal
from aios.crypto.fear_greed import FearGreed
from aios.crypto.fear_greed_client import FearGreedClient
from aios.crypto.rsi_calculator import RsiCalculator
from aios.crypto.signal_rule import SignalRule

log = logging.getLogger(__name__)

MAX_COINS = 5


class CryptoSignalService:
    """Buy/hold/sell signals from momentum, RSI(14) and the Fear & Greed index.

    Every number is fetched fresh; a source that fails is reported as missing
    rather than guessed.
    """

    def __init__(
        self,
        gecko: CoinGeckoClient,
        fear_greed: FearGreedClient,
        rsi: RsiCalculator,
        rule: SignalRule,
    ) -> None:
        self._gecko = gecko
        self._fear_greed = fear_greed
        self._rsi = rsi
        self._rule = rule

    async def signals(self, coins: list[str]) -> list[CoinSignal]:
        ids = (await self._gecko.resolve_ids(coins or ["bitcoin", "ethereum"]))[:MAX_COINS]
        markets = await self._gecko.markets(ids)
        fear_greed = await self._fear_greed_or_none()
        results = []
        for market in markets:
            rsi = await self._rsi_or_none(market.id)
            call = self._rule.decide(rsi, fear_greed.value if fear_greed else None)
            results.append(CoinSignal(market=market, rsi_14=rsi, fear_greed=fear_greed, call=call))
        return results

    async def _fear_greed_or_none(self) -> FearGreed | None:
        try:
            return await self._fear_greed.current()
        except Exception as exc:
            log.warning("fear & greed unavailable: %s", exc)
            return None

    async def _rsi_or_none(self, coin_id: str) -> float | None:
        try:
            return self._rsi.rsi(await self._gecko.daily_closes(coin_id))
        except Exception as exc:
            log.warning("RSI unavailable for %s: %s", coin_id, exc)
            return None
