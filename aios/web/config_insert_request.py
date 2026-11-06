from typing import Any

from pydantic import BaseModel, Field


class ConfigInsertRequest(BaseModel):
    """A key from the reference, to be written into aios.yaml's text as it is being
    edited: where (`path`) and with which value (its default)."""

    text: str
    path: list[str] = Field(min_length=1)
    value: Any = None
