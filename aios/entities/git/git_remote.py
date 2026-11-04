from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class GitRemote(BaseModel):
    """Where the configuration repository is pushed, and how ai-os signs in there.
    `id` is the remote's name (`origin`). Kept in the data dir, never in the
    repository itself; the key and the token are encrypted."""

    id: str = "origin"
    url: str
    auth: Literal["ssh", "token", "none"] = "ssh"
    public_key: str | None = None
    private_key: str | None = None
    """An OpenSSH private key, encrypted."""
    token: str | None = None
    """A GitHub token, encrypted."""
    auto_push: bool = False
    updated_at: datetime | None = None
    updated_by: str | None = None
