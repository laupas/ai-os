from abc import ABC, abstractmethod
from typing import Any


class AppendLog(ABC):
    """Append-only records, e.g. the messages of one conversation."""

    @abstractmethod
    async def append(self, log: str, record: dict[str, Any]) -> None: ...

    @abstractmethod
    async def read_all(self, log: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete(self, log: str) -> None:
        """Removes the whole log; nothing happens if there is none."""
