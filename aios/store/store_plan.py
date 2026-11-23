from pydantic import BaseModel

from aios.store.store_item import StoreItem
from aios.store.store_ref import StoreRef
from aios.variables.variable_field import VariableField


class StorePlan(BaseModel):
    """What installing an item would do: what it brings, what is there already,
    what neither the source nor the installation has, and what it asks for."""

    item: StoreItem
    install: list[StoreItem]
    """Requirements first, the item last, so whatever it uses exists before it."""
    kept: list[StoreRef] = []
    missing: list[StoreRef] = []
    variables: list[VariableField] = []

    @property
    def code(self) -> bool:
        return any(i.code_folder is not None for i in self.install)
