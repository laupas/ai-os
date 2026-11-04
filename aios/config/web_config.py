from pydantic import BaseModel

from aios.config.web_auth_config import WebAuthConfig


class WebConfig(BaseModel):
    """The web console. Off unless `enabled`.

    It sits behind a login proxy, and who is asking is checked here again (see
    `auth`): anything on the network may reach the port directly, past the proxy.
    Without `auth` (or the older `access_*` / `dev_email`) every request is refused.
    """

    enabled: bool = False
    port: int = 8080
    auth: WebAuthConfig | None = None
    access_team_domain: str | None = None
    """Older form of `auth: {mode: cloudflare, team_domain: …}`, still read."""
    access_aud: str | None = None
    """Older form of `auth.audience` for Cloudflare, still read."""
    public_url: str | None = None
    """Where browsers reach the console, e.g. https://ai-os.example.com; used for
    OAuth redirects. Unset, it is taken from the request's host."""
    dev_email: str | None = None
    """Only for running locally: treat every request as this address. Never set it
    on a deployed instance."""
