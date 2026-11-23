from pydantic import BaseModel

from aios.store.store_kind import StoreKind


class StoreRef(BaseModel, frozen=True):
    """One item by kind and id, in a source or installed."""

    kind: StoreKind
    id: str

    @classmethod
    def parse(cls, text: str) -> "StoreRef":
        """`connectors/github` (the folder) or `connector:github`."""
        collection, sep, item = text.replace(":", "/", 1).partition("/")
        if not sep or not item:
            raise ValueError(f"not an item: {text!r}; write e.g. connectors/github")
        plural = collection.endswith("s")
        kind = StoreKind.of_collection(collection) if plural else StoreKind(collection)
        return cls(kind=kind, id=item)

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.id}"
