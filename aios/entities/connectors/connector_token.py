from datetime import datetime

from pydantic import BaseModel


class ConnectorToken(BaseModel):
    """The OAuth sign-in of one connector: the tokens, and what is needed to renew
    them. `id` is the connector's name. A secret: kept in the data dir, never in the
    configuration repository and never sent to the console."""

    id: str
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    token_endpoint: str
    client_id: str
    client_secret: str | None = None
    auth_method: str = "none"
    """How the client authenticates at the token endpoint: client_secret_basic,
    client_secret_post or none."""
    resource: str | None = None
    signed_in_by: str | None = None
    signed_in_at: datetime | None = None
