from typing import Literal

from pydantic import BaseModel


class RemoteRequest(BaseModel):
    """The remote as the console sends it; `token` left out keeps the stored one."""

    url: str
    auth: Literal["ssh", "token", "none"] = "ssh"
    token: str | None = None
    auto_push: bool = False
