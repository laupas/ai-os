from pydantic import BaseModel

from aios.storage.collection import Collection
from aios.storage.collection_registry import CollectionRegistry
from aios.tools.tool_error import ToolError


class CollectionAccessGuard:
    """Hands out a collection only within the agent access its definition grants,
    and of an owned collection only the documents of the turn user and shared ones."""

    def __init__(self, registry: CollectionRegistry) -> None:
        self._registry = registry

    def readable(self, name: str) -> Collection[BaseModel]:
        collection = self._registry.get(name)
        if collection is None or not collection.definition.agent_access.allows_read():
            raise ToolError(f"No readable collection called {name!r}.")
        return collection

    def writable(self, name: str) -> Collection[BaseModel]:
        collection = self.readable(name)
        if not collection.definition.agent_access.allows_write():
            raise ToolError(f"The collection {name!r} is read-only for agents.")
        return collection

    def readable_names(self) -> list[str]:
        return [c.name for c in self._registry.all() if c.definition.agent_access.allows_read()]

    @staticmethod
    def visible(collection: Collection[BaseModel], user_id: str) -> list[BaseModel]:
        return collection.filter(lambda item: collection.definition.visible_to(item, user_id))

    @staticmethod
    def get_visible(
        collection: Collection[BaseModel], item_id: str, user_id: str
    ) -> BaseModel | None:
        item = collection.get(item_id)
        if item is None or not collection.definition.visible_to(item, user_id):
            return None
        return item
