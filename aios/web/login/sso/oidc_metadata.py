from pydantic import BaseModel


class OidcMetadata(BaseModel):
    """What a provider's discovery document says about signing in with it."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
