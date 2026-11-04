from typing import Any

from aios.crypto.crypto_signal_service import CryptoSignalService
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext


class CryptoSignalTool(AiosTool):
    def __init__(self, signals: CryptoSignalService) -> None:
        self._signals = signals

    @property
    def name(self) -> str:
        return "crypto_signal"

    @property
    def description(self) -> str:
        return (
            "Buy/hold/sell signal per coin from live price momentum, RSI(14) and the crypto "
            "Fear & Greed index. Default coins: bitcoin, ethereum. Max 5. Returns JSON."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coins": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tickers or CoinGecko ids, e.g. BTC, eth, solana",
                }
            },
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        signals = await self._signals.signals([str(c) for c in args.get("coins") or []])
        return "[" + ",".join(s.model_dump_json() for s in signals) + "]"
