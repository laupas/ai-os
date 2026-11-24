from datetime import datetime

from pydantic import BaseModel


class WebSession(BaseModel):
    """A browser signed in with the console's own login. `id` is the SHA-256 of
    the token in its cookie: the token itself is kept nowhere, so the data dir
    cannot be turned into sessions. In the data dir, never in git."""

    id: str
    user_id: str
    mode: str
    """The login it came from; a session of another mode does not count."""
    stamp: str = ""
    """The login's stamp for the user (a password's); when it changes, the session ends."""
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    idle_minutes: int | None = None
    """Ends after this long without a request; None: only at `expires_at`."""
    user_agent: str = ""
    address: str = ""
    """Where it signed in from, as the request said."""
