from typing import Any

from aios.crypto.kraken_trader import KrakenTrader
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext

ORDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "side": {"type": "string", "enum": ["buy", "sell"]},
        "coin": {"type": "string", "enum": ["BTC", "ETH"]},
        "chf": {"type": "number", "description": "Order size in CHF"},
    },
    "required": ["side", "coin", "chf"],
}


class CryptoQuoteTool(AiosTool):
    """A price and what the limits say, without trading."""

    def __init__(self, trader: KrakenTrader) -> None:
        self._trader = trader

    @property
    def name(self) -> str:
        return "crypto_quote"

    @property
    def description(self) -> str:
        return (
            "Quote a Kraken spot market order in CHF without placing it: price, expected "
            "volume, fee estimate, today's usage, and whether the limits would block it."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return ORDER_SCHEMA

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        quote = await self._trader.quote(str(args["side"]), str(args["coin"]), float(args["chf"]))
        return quote.model_dump_json()
