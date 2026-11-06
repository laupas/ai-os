from pydantic import BaseModel


class OAuthClientConfig(BaseModel):
    """A connector's own OAuth client, for a server that neither publishes its
    OAuth endpoints nor lets clients register themselves (Google's MCP servers).

    Written as `oauth:` inside the connector's config, with `${VAR}` for the id and
    secret; ai-os takes it out before the config reaches Claude Code. With it, a
    sign-in skips discovery and registration and uses these values instead.
    """

    authorization_endpoint: str
    token_endpoint: str
    client_id: str
    client_secret: str | None = None
    auth_method: str = "client_secret_post"
    scopes: list[str] = []
    params: dict[str, str] = {}
    """Extra authorization parameters, e.g. Google's `access_type: offline`."""
