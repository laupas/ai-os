from datetime import datetime

from pydantic import BaseModel

from aios.connectors.oauth_metadata import OAuthMetadata


class PendingSignIn(BaseModel):
    """A sign-in between sending the browser to the server and its return."""

    connector: str
    user_id: str
    verifier: str
    redirect_uri: str
    metadata: OAuthMetadata
    client_id: str
    client_secret: str | None = None
    auth_method: str
    started_at: datetime
