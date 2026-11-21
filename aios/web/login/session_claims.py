from pydantic import BaseModel


class SessionClaims(BaseModel):
    """What a console session cookie says, once its signature is checked."""

    user_id: str
    mode: str
    stamp: str
    expires: float
    """Seconds since the epoch."""
