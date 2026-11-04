from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from aios.storage.collection_definition import CollectionDefinition
from aios.storage.document_store import DocumentStore


class Collection[T: BaseModel]:
    """Typed access to one collection, with every document held in memory.

    `load()` reads the collection once at startup; every write goes to the store
    and the in-memory copy, so lookups never touch the disk. Entities need an `id`.
    """

    def __init__(self, definition: CollectionDefinition, store: DocumentStore) -> None:
        self._definition = definition
        self._store = store
        self._items: dict[str, T] = {}

    @property
    def definition(self) -> CollectionDefinition:
        return self._definition

    @property
    def name(self) -> str:
        return self._definition.name

    async def load(self) -> None:
        documents = await self._store.list(self.name)
        items: dict[str, T] = {}
        for document in documents:
            item = self.parse(document)
            items[item.id] = item  # type: ignore[attr-defined]
        # Swapped in whole: a document that fails to parse leaves the old set intact.
        self._items = items

    def parse(self, document: dict[str, Any]) -> T:
        return self._definition.entity.model_validate(document)  # type: ignore[return-value]

    def get(self, item_id: str) -> T | None:
        return self._items.get(item_id)

    def all(self) -> list[T]:
        return list(self._items.values())

    def find(self, predicate: Callable[[T], bool]) -> T | None:
        return next((i for i in self._items.values() if predicate(i)), None)

    def filter(self, predicate: Callable[[T], bool]) -> list[T]:
        return [i for i in self._items.values() if predicate(i)]

    def is_empty(self) -> bool:
        return not self._items

    async def put(self, item: T) -> T:
        item_id: str = item.id  # type: ignore[attr-defined]
        await self._store.put(self.name, item_id, item.model_dump(mode="json"))
        self._items[item_id] = item
        return item

    async def delete(self, item_id: str) -> None:
        await self._store.delete(self.name, item_id)
        self._items.pop(item_id, None)
