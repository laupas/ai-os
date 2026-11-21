from datetime import datetime

from pydantic import BaseModel


class PendingCode(BaseModel):
    """A sign-in code sent to a user and not used yet."""

    code: str
    expires: datetime
    sent: datetime
    tries: int = 0
