from pydantic import BaseModel

from aios.store.store_kind import StoreKind


class StoreUpdateRequest(BaseModel):
    """An installed item, by the id it has here, brought to what its source offers
    now: a copy (`StoreConnectorCopy`) included."""

    kind: StoreKind
    id: str
    trust_code: bool = False
