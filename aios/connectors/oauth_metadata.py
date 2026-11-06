from pydantic import BaseModel


class OAuthMetadata(BaseModel):
    """What a server's OAuth discovery says, as far as signing in needs it."""

    resource: str | None = None
    """RFC 8707 resource; None for a configured client, which is sent none."""
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None = None
    auth_methods: list[str] = ["client_secret_basic"]
    scopes: list[str] = []
    params: dict[str, str] = {}
