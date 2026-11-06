from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class WebAuthConfig(BaseModel):
    """How the web console learns who is asking: always from a login proxy in front
    of it, never from a password of its own.

    - `cloudflare`: Cloudflare Access's signed token (`team_domain`, `audience`);
    - `jwt`: any proxy that forwards a signed token (oauth2-proxy, Authentik,
      Pomerium, …): `header`, `jwks_url`, `issuer`, `audience`, `email_claim`;
    - `header`: a proxy that forwards the address as a plain header (Authelia,
      Traefik forward-auth, …). A plain header can be forged by anything that
      reaches ai-os directly, so it is only believed from `trusted_proxies` and/or
      with the secret named by `secret_env` in `secret_header`;
    - `dev`: every request is `dev_email`. Only on your own machine.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    mode: Literal["cloudflare", "jwt", "header", "dev"]
    team_domain: str | None = None
    """cloudflare: e.g. `example.cloudflareaccess.com`."""
    audience: str | None = None
    """cloudflare, jwt: the expected `aud` (Access: the application's AUD tag)."""
    header: str | None = None
    """jwt, header: where the proxy puts the token or the address."""
    jwks_url: str | None = None
    issuer: str | None = None
    email_claim: str = "email"
    algorithms: list[str] = ["RS256", "ES256"]
    trusted_proxies: list[str] = []
    """header: addresses or networks (CIDR) the proxy connects from."""
    secret_header: str = "X-Aios-Proxy-Secret"
    secret_env: str | None = None
    """header: the environment variable holding a secret the proxy also sends.
    The name, never the value: this file is in git."""
    dev_email: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> "WebAuthConfig":
        needs = {
            "cloudflare": ["team_domain", "audience"],
            "jwt": ["header", "jwks_url", "issuer", "audience"],
            "header": ["header"],
            "dev": ["dev_email"],
        }[self.mode]
        missing = [name for name in needs if not getattr(self, name)]
        if missing:
            raise ValueError(f"web.auth mode {self.mode} needs {', '.join(missing)}")
        if self.mode == "header" and not (self.trusted_proxies or self.secret_env):
            raise ValueError(
                "web.auth mode header needs trusted_proxies or secret_env: "
                "a plain header is forged by anything that reaches ai-os directly"
            )
        return self
