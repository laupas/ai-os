import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coin_gecko_client import CoinGeckoClient
from crypto_signal_service import CryptoSignalService
from fear_greed_client import FearGreedClient
from http_json import HttpJson
from kraken_client import KrakenClient
from kraken_error import KrakenError
from kraken_trader import KrakenTrader
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from rsi_calculator import RsiCalculator
from signal_rule import SignalRule
from trade_limit_guard import TradeLimitGuard
from trade_limits import TradeLimits
from trade_log import TradeLog


def _secret(env: dict[str, str], name: str) -> str | None:
    # A variable that is set nowhere reaches us as its own `${NAME}`.
    value = env.get(name, "")
    return None if not value or value.startswith("${") else value


class CryptoConnector:
    """Kraken spot trading in CHF inside hard limits, and buy/hold/sell signals.

    Everything comes from the environment ai-os starts it with: the settings
    (`AIOS_CONNECTOR_SETTINGS`, the trading limits), where to keep the trade log
    (`AIOS_CONNECTOR_STATE`), the user's timezone, and the Kraken key.
    """

    def __init__(self, env: dict[str, str]) -> None:
        self.limits = TradeLimits.model_validate(
            json.loads(env.get("AIOS_CONNECTOR_SETTINGS") or "{}")
        )
        http = HttpJson()
        trades = TradeLog(Path(env.get("AIOS_CONNECTOR_STATE") or "."))
        self.guard = TradeLimitGuard(
            self.limits, trades, lambda: datetime.now(UTC), env.get("AIOS_TIMEZONE") or "UTC"
        )
        self.trades = trades
        self.trader = KrakenTrader(
            KrakenClient(http, _secret(env, "KRAKEN_API_KEY"), _secret(env, "KRAKEN_API_SECRET")),
            self.guard,
            self.limits,
            trades,
            lambda: datetime.now(UTC),
        )
        self.signals = CryptoSignalService(
            CoinGeckoClient(http), FearGreedClient(http), RsiCalculator(), SignalRule()
        )

    @classmethod
    def from_environment(cls) -> "CryptoConnector":
        return cls(dict(os.environ))

    def preflight(self, tool: str, arguments: dict[str, Any]) -> dict[str, str]:
        """Before a human is asked about `trade`: refuse what the limits refuse."""
        if tool != "trade":
            return {"ask": f"Allow crypto {tool}?"}
        side = str(arguments.get("side", ""))
        coin = str(arguments.get("coin", "")).upper()
        try:
            chf = float(arguments.get("chf", 0))
        except (TypeError, ValueError):
            return {"deny": "The order needs a numeric CHF amount."}
        reason = self.guard.check_order(side, coin, chf)
        if reason:
            return {"deny": f"The trading limits refuse this order: {reason}."}
        return {"ask": f"Place a market order on Kraken: {side} {coin} for {chf:.2f} CHF?"}

    def server(self) -> MCPServer:
        server = MCPServer("crypto")

        @server.tool()
        async def signal(coins: list[str] | None = None) -> str:
            """Buy/hold/sell signal per coin from live price momentum, RSI(14) and the
            crypto Fear & Greed index. Tickers or CoinGecko ids; default bitcoin and
            ethereum, at most 5."""
            result = await self.signals.signals([str(c) for c in coins or []])
            return "[" + ",".join(s.model_dump_json() for s in result) + "]"

        @server.tool()
        async def quote(side: str, coin: str, chf: float) -> str:
            """Quote a Kraken spot market order in CHF without placing it: price,
            expected volume, fee estimate, today's usage, and whether the limits would
            block it. side is buy or sell; coin e.g. BTC."""
            return (await self.trader.quote(side, coin, chf)).model_dump_json()

        @server.tool()
        async def trade(side: str, coin: str, chf: float) -> str:
            """Place a Kraken spot market order in CHF. Needs the user's approval,
            which is asked automatically. Real money: only when the user asked."""
            try:
                placed = await self.trader.execute(side, coin, chf)
            except KrakenError as exc:
                raise ToolError(f"Order not placed: {exc}") from exc
            return placed.model_dump_json()

        @server.tool()
        async def balance() -> str:
            """The Kraken account's CHF, BTC and ETH balances."""
            try:
                return json.dumps(await self.trader.balance())
            except KrakenError as exc:
                raise ToolError(str(exc)) from exc

        @server.tool()
        async def trades(limit: int = 20) -> str:
            """The latest orders this connector placed, newest first."""
            done = sorted(self.trades.all(), key=lambda t: t.executed_at, reverse=True)
            return "[" + ",".join(t.model_dump_json() for t in done[: max(1, limit)]) + "]"

        return server
