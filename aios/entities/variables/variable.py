from datetime import datetime

from pydantic import BaseModel


class Variable(BaseModel):
    """A named value connectors refer to as `${NAME}` (or `${file:NAME}` for a file
    holding it), set in the console. `id` is the name.

    A secret's value is stored encrypted and never shown again once set. Kept in
    the data dir, never in the configuration repository.
    """

    id: str
    value: str
    """The value, or for a secret its ciphertext."""
    secret: bool = False
    file: bool = False
    """Used as a file: `${file:NAME}` stands for the path of a file holding the value."""
    description: str = ""
    updated_at: datetime | None = None
    updated_by: str | None = None
