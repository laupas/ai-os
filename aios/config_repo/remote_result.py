from datetime import datetime

from pydantic import BaseModel


class RemoteResult(BaseModel):
    """How the last exchange with the remote went."""

    action: str
    ok: bool
    message: str = ""
    at: datetime
