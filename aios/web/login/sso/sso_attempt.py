from datetime import datetime

from pydantic import BaseModel


class SsoAttempt(BaseModel):
    """A sign-in sent to a provider and not back yet."""

    provider: str
    nonce: str
    verifier: str
    """PKCE: the provider gets only its hash, the token request the value."""
    redirect_uri: str
    expires: datetime
