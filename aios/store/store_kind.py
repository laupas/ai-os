from enum import StrEnum


class StoreKind(StrEnum):
    """What a store item is, and so which collection and folder it belongs to."""

    AGENT = "agent"
    SKILL = "skill"
    CONNECTOR = "connector"
    TRIGGER = "trigger"

    @property
    def collection(self) -> str:
        return f"{self.value}s"

    @classmethod
    def of_collection(cls, name: str) -> "StoreKind":
        return cls(name.removesuffix("s"))
