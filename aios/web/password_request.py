from pydantic import BaseModel


class PasswordRequest(BaseModel):
    """A new console password; `current` when changing one's own."""

    password: str
    current: str | None = None
