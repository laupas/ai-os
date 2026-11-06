from datetime import datetime

from pydantic import BaseModel

from aios.connectors.oauth_metadata import OAuthMetadata


class PendingSignIn(BaseModel):
    """A sign-in between sending the browser to the server and its return."""

    connector: str
    user_id: str
    """Who started it; only they may finish it."""
    for_user: str | None = None
    """Whose account it signs in: the starter's own, or None for the shared one."""
    verifier: str
    redirect_uri: str
    metadata: OAuthMetadata
    client_id: str
    client_secret: str | None = None
    auth_method: str
    started_at: datetime
