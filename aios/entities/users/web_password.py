from datetime import datetime

from pydantic import BaseModel


class WebPassword(BaseModel):
    """A user's password for the console's own login (`web.auth.mode: password`).
    `id` is the user's id. Only the hash is kept, in the data dir, never in git."""

    id: str
    hash: str
    updated_at: datetime | None = None
    updated_by: str | None = None
