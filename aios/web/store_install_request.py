from pydantic import BaseModel

from aios.store.store_kind import StoreKind


class StoreInstallRequest(BaseModel):
    source: str
    kind: StoreKind
    id: str
    variables: dict[str, str] = {}
    """Values for the variables the install asks for; an empty one is left as it is."""
    replace: bool = False
    trust_code: bool = False
