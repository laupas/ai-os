from aios.storage.agent_access import AgentAccess
from aios.storage.collection_definition import CollectionDefinition


class CollectionAccessOverrides:
    """Applies the `collection_access` settings from config.yaml to a definition."""

    def __init__(self, overrides: dict[str, AgentAccess]) -> None:
        self._overrides = overrides
        self._defaults: dict[str, AgentAccess] = {}

    def apply(self, definition: CollectionDefinition) -> CollectionDefinition:
        self._defaults[definition.name] = definition.agent_access
        access = self._overrides.get(definition.name)
        if access is None:
            return definition
        return definition.model_copy(update={"agent_access": access})

    def defaults(self) -> dict[str, AgentAccess]:
        """The collections this may change, with their own access: only those
        passed through `apply`. The configuration collections never are."""
        return dict(self._defaults)
