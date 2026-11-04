from typing import Any

from aios.crypto.kraken_error import KrakenError
from aios.crypto.kraken_trader import KrakenTrader
from aios.tools.aios_tool import AiosTool
from aios.tools.crypto_quote_tool import ORDER_SCHEMA
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class CryptoTradeTool(AiosTool):
    """Places a real order. Always approved by a human first (`CryptoTradeApprovalRule`),
    and always inside the trading limits, which are checked again here."""

    NAME = "crypto_trade"

    def __init__(self, trader: KrakenTrader) -> None:
        self._trader = trader

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Place a Kraken spot market order in CHF (BTC or ETH). Needs the user's "
            "approval, which is asked automatically. Real money: only when the user asked."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return ORDER_SCHEMA

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        try:
            trade = await self._trader.execute(
                str(args["side"]), str(args["coin"]), float(args["chf"])
            )
        except KrakenError as exc:
            raise ToolError(f"Order not placed: {exc}") from exc
        return trade.model_dump_json()
