from pydantic import BaseModel

from aios.store.store_kind import StoreKind


class StoreLinkRequest(BaseModel):
    """An item made here, recorded as installed from what `source` offers under the
    same id, unchanged."""

    source: str
    kind: StoreKind
    id: str
