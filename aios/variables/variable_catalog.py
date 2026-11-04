import re

from aios.agents.catalog_error import CatalogError
from aios.common.clock import Clock
from aios.entities.variables.variable import Variable
from aios.storage.collection import Collection
from aios.variables.secret_box import SecretBox

NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class VariableCatalog:
    """Setting and removing variables. A secret is encrypted on the way in and
    never read back out here; only the resolver decrypts, when a connector starts."""

    def __init__(self, variables: Collection[Variable], box: SecretBox, clock: Clock) -> None:
        self._variables = variables
        self._box = box
        self._clock = clock

    def all(self) -> list[Variable]:
        return sorted(self._variables.all(), key=lambda v: v.id)

    def get(self, name: str) -> Variable | None:
        return self._variables.get(name)

    async def save(
        self,
        name: str,
        value: str | None,
        secret: bool,
        file: bool,
        description: str,
        author: str,
    ) -> Variable:
        """`value` None keeps the current one, which is how a secret is edited
        without being shown: its description or kind change, its value does not."""
        if not NAME.match(name):
            raise CatalogError("a name is upper-case letters, digits and _, starting with a letter")
        current = self._variables.get(name)
        if value is None:
            if current is None:
                raise CatalogError("a new variable needs a value")
            if current.secret != secret:
                raise CatalogError("turning a value secret or back needs the value again")
            stored = current.value
        else:
            stored = self._box.encrypt(value) if secret else value
        return await self._variables.put(
            Variable(
                id=name,
                value=stored,
                secret=secret,
                file=file,
                description=description,
                updated_at=self._clock.now(),
                updated_by=author,
            )
        )

    async def delete(self, name: str) -> None:
        await self._variables.delete(name)
