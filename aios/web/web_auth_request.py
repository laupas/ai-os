from pydantic import BaseModel

from aios.config.web_auth_config import WebAuthConfig


class WebAuthRequest(BaseModel):
    """The console's login as Settings send it, to try or to save."""

    auth: WebAuthConfig
    public_url: str | None = None
