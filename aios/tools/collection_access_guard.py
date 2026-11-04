from pydantic import BaseModel

from aios.storage.collection import Collection
from aios.storage.collection_registry import CollectionRegistry
from aios.tools.tool_error import ToolError


class CollectionAccessGuard:
    """Hands out a collection only within the agent access its definition grants."""

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
