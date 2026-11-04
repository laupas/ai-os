import json
from typing import Any

from aios.crypto.kraken_error import KrakenError
from aios.crypto.kraken_trader import KrakenTrader
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class CryptoBalanceTool(AiosTool):
    def __init__(self, trader: KrakenTrader) -> None:
        self._trader = trader

    @property
    def name(self) -> str:
        return "crypto_balance"

    @property
    def description(self) -> str:
        return "The Kraken account's CHF, BTC and ETH balances."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        try:
            return json.dumps(await self._trader.balance())
        except KrakenError as exc:
            raise ToolError(str(exc)) from exc
