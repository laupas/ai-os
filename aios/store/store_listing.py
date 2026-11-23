from datetime import datetime

from pydantic import BaseModel

from aios.store.store_item import StoreItem
from aios.store.store_ref import StoreRef


class StoreListing(BaseModel):
    """What one source offers, as last fetched."""

    url: str
    branch: str | None = None
    name: str = ""
    description: str = ""
    items: list[StoreItem] = []
    problems: list[str] = []
    """Items that could not be read, each with why."""
    error: str | None = None
    """Why the source could not be fetched; its items are the last ones fetched."""
    fetched_at: datetime | None = None

    def get(self, ref: StoreRef) -> StoreItem | None:
        return next((i for i in self.items if i.ref == ref), None)
