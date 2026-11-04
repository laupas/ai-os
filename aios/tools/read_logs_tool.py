from datetime import timedelta
from typing import Any

from aios.common.clock import Clock
from aios.logs.log_reader import LogReader
from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext


class ReadLogsTool(AiosTool):
    def __init__(self, reader: LogReader, clock: Clock) -> None:
        self._reader = reader
        self._clock = clock

    @property
    def name(self) -> str:
        return "read_logs"

    @property
    def description(self) -> str:
        return (
            "Read ai-os's own log lines from the last `hours` (default 24) at or above "
            "`min_level` (default WARNING). Tracebacks come with their line. Times are UTC."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hours": {"type": "number"},
                "min_level": {"type": "string", "enum": ["INFO", "WARNING", "ERROR"]},
            },
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        since = self._clock.now() - timedelta(hours=float(args.get("hours") or 24))
        lines = self._reader.read(since, str(args.get("min_level") or "WARNING"))
        return "\n".join(lines) if lines else "No matching log lines."
