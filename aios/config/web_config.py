from pydantic import BaseModel, ConfigDict

from aios.config.web_auth_config import WebAuthConfig


class WebConfig(BaseModel):
    """The web console, on unless `enabled: false`.

    Who is asking is decided by `auth`: the console's own login page, or a login
    proxy whose word is checked here again, since anything on the network may reach
    the port directly. Without `auth` (or the older `access_*` / `dev_email`) the
    console uses `pick`, so a fresh ai-os can be signed in to at once: keep it off
    any network you do not trust until a real login is set.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = True
    port: int = 8080
    auth: WebAuthConfig | None = None
    access_team_domain: str | None = None
    """Older form of `auth: {mode: cloudflare, team_domain: …}`, still read."""
    access_aud: str | None = None
    """Older form of `auth.audience` for Cloudflare, still read."""
    public_url: str | None = None
    """Where browsers reach the console, e.g. https://ai-os.example.com; used for
    OAuth redirects. Unset, it is taken from the request's host."""
    trusted_proxies: list[str] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    ]
    """Addresses or networks (CIDR) of the proxies in front (Traefik, a tunnel).
    Only from these is the client's address in `CF-Connecting-IP`, `X-Real-IP` or
    `X-Forwarded-For` believed; from anywhere else the connection's own address
    counts, so nobody can pose as another address. Default: private networks."""
    dev_email: str | None = None
    """Only for running locally: treat every request as this address. Never set it
    on a deployed instance."""

    def effective_auth(self) -> WebAuthConfig:
        """`auth`, or what the older keys mean, or `pick` when nothing is set."""
        if self.auth is not None:
            return self.auth
        if self.access_team_domain and self.access_aud:
            return WebAuthConfig(
                mode="cloudflare", team_domain=self.access_team_domain, audience=self.access_aud
            )
        if self.dev_email:
            return WebAuthConfig(mode="dev", dev_email=self.dev_email)
        return WebAuthConfig(mode="pick")
