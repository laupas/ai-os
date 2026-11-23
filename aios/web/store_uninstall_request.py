from pydantic import BaseModel

from aios.store.store_kind import StoreKind


class StoreUninstallRequest(BaseModel):
    kind: StoreKind
    id: str
