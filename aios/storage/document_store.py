from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DocumentStore(ABC):
    """Replaceable JSON documents, grouped in collections."""

    @abstractmethod
    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, collection: str, doc_id: str) -> None: ...

    @abstractmethod
    async def list(self, collection: str) -> list[dict[str, Any]]: ...
