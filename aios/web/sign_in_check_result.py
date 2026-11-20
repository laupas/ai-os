from pydantic import BaseModel


class SignInCheckResult(BaseModel):
    """What a one-line call to Claude with one credential showed."""

    ok: bool
    error: str | None = None
    """Why it failed, as the CLI put it; never the credential."""
    model: str | None = None
    seconds: float = 0
