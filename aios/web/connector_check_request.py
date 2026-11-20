from typing import Any

from pydantic import BaseModel


class ConnectorCheckRequest(BaseModel):
    """What the console has typed but not saved, tried by a code connector's check:
    its settings (None: the stored ones) and values for its declared variables."""

    settings: dict[str, Any] | None = None
    variables: dict[str, str] = {}
