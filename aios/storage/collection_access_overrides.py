from aios.storage.agent_access import AgentAccess
from aios.storage.collection_definition import CollectionDefinition


class CollectionAccessOverrides:
    """Applies the `collection_access` settings from config.yaml to a definition."""

    def __init__(self, overrides: dict[str, AgentAccess]) -> None:
        self._overrides = overrides

    def apply(self, definition: CollectionDefinition) -> CollectionDefinition:
        access = self._overrides.get(definition.name)
        if access is None:
            return definition
        return definition.model_copy(update={"agent_access": access})
