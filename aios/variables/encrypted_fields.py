from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from aios.storage.collection import Collection


class EncryptedFields(BaseModel):
    """Which fields of a collection's documents hold encrypted secrets, so a new key
    can be applied to all of them (`SecretsKeyRotation`). A new kind of stored secret
    is one more of these, registered in `ApplicationContainer`."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    collection: Collection[Any]
    fields: tuple[str, ...]
    label: str
    """What a document is, for people: "variable", "connector sign-in"."""
    applies: Callable[[Any], bool] = lambda document: True
    """Whether a document's fields are encrypted at all (a variable that is no secret)."""
