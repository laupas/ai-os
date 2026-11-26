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
    name: str | None = None
    """A connector only: installed under this name, beside the one of its own, with
    variables of its own. `variables` still name the source's variables."""
