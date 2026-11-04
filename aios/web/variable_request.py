from pydantic import BaseModel


class VariableRequest(BaseModel):
    """A variable as the console sends it. `name` is read only when creating one;
    `value` left out keeps the current one (how a secret is edited unseen)."""

    name: str | None = None
    value: str | None = None
    secret: bool = False
    file: bool = False
    description: str = ""
