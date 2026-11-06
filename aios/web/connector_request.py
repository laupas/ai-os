from typing import Any

from pydantic import BaseModel, Field

from aios.entities.connectors.sign_in_mode import SignInMode


class ConnectorRequest(BaseModel):
    """A connector as the console sends it. `name` is read only when creating one."""

    name: str | None = None
    description: str = ""
    config: dict[str, Any] = Field(min_length=1)
    enabled: bool = True
    sign_in: SignInMode | None = None
    """None keeps what the connector has (shared for a new one)."""
    shared_fallback: bool | None = None
