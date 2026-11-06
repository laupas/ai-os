import json
from pathlib import Path

from trade import Trade


class TradeLog:
    """Every executed order, one JSON line each, in the connector's state folder.
    The limits are counted from it, so it is never pruned."""

    def __init__(self, folder: Path) -> None:
        self._file = Path(folder) / "trades.jsonl"

    def all(self) -> list[Trade]:
        if not self._file.exists():
            return []
        lines = self._file.read_text("utf-8").splitlines()
        return [Trade.model_validate_json(line) for line in lines if line.strip()]

    def add(self, trade: Trade) -> Trade:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with self._file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trade.model_dump(mode="json")) + "\n")
        return trade
