from typing import Any

from pydantic import BaseModel, Field


class ConnectorRequest(BaseModel):
    """A connector as the console sends it. `name` is read only when creating one."""

    name: str | None = None
    description: str = ""
    config: dict[str, Any] = Field(min_length=1)
    enabled: bool = True
