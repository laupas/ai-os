from pydantic import BaseModel

from aios.storage.collection import Collection


class CollectionRegistry:
    """Every collection known to the system, by name."""

    def __init__(self, collections: list[Collection[BaseModel]]) -> None:
        self._collections = {c.name: c for c in collections}

    def get(self, name: str) -> Collection[BaseModel] | None:
        return self._collections.get(name)

    def all(self) -> list[Collection[BaseModel]]:
        return list(self._collections.values())

    async def load_all(self) -> None:
        for collection in self._collections.values():
            await collection.load()
