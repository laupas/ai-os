from pydantic import BaseModel


class CodeConnectorOption(BaseModel):
    """One choice a code connector offers for a setting: what is stored, and what
    the console shows beside it."""

    value: str
    label: str = ""
