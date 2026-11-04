import copy
from typing import Any

from aios.storage.append_log import AppendLog
from aios.storage.storage_name import StorageName


class InMemoryAppendLog(AppendLog):
    """Keeps log records in a dict. For tests and throwaway runs."""

    def __init__(self) -> None:
        self._logs: dict[str, list[dict[str, Any]]] = {}

    async def append(self, log: str, record: dict[str, Any]) -> None:
        StorageName.check_path(log)
        self._logs.setdefault(log, []).append(copy.deepcopy(record))

    async def read_all(self, log: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self._logs.get(log, []))

    async def delete(self, log: str) -> None:
        StorageName.check_path(log)
        self._logs.pop(log, None)
