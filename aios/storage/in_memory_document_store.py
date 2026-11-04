from __future__ import annotations

import copy
from typing import Any

from aios.storage.document_store import DocumentStore
from aios.storage.storage_name import StorageName


class InMemoryDocumentStore(DocumentStore):
    """Keeps documents in a dict. For tests and throwaway runs."""

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        document = self._collections.get(collection, {}).get(doc_id)
        return copy.deepcopy(document)

    async def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        StorageName.check(collection)
        StorageName.check(doc_id)
        self._collections.setdefault(collection, {})[doc_id] = copy.deepcopy(data)

    async def delete(self, collection: str, doc_id: str) -> None:
        self._collections.get(collection, {}).pop(doc_id, None)

    async def list(self, collection: str) -> list[dict[str, Any]]:
        documents = self._collections.get(collection, {})
        return [copy.deepcopy(documents[k]) for k in sorted(documents)]
