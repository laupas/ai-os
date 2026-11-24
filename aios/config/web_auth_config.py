from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aios.config.sso_provider import SsoProvider

PROXIES = ("cloudflare", "jwt", "header")


class WebAuthConfig(BaseModel):
    """How the web console learns who is asking: from a login proxy in front of it,
    or from its own login page.

    - `cloudflare`: Cloudflare Access's signed token (`team_domain`, `audience`);
    - `jwt`: any proxy that forwards a signed token (oauth2-proxy, Authentik,
      Pomerium, …): `header`, `jwks_url`, `issuer`, `audience`, `email_claim`;
    - `header`: a proxy that forwards the address as a plain header (Authelia,
      Traefik forward-auth, …). A plain header can be forged by anything that
      reaches ai-os directly, so it is only believed from `trusted_proxies` and/or
      with the secret named by `secret_env` in `secret_header`;
    - `pick`: a login page lists the users with a web account, and whoever opens it
      picks one, with no password. Only where everyone who can reach the console
      is trusted (a home network);
    - `password`: a login page asks for a name and a password, set per user in the
      console. Passwords are hashed in the data dir, never in git;
    - `code`: a login page asks for a name and sends a one-time code to that user's
      chat account (Slack, Teams, Signal, mail);
    - `sso`: a login page with a button per provider in `providers` (Microsoft
      365, Google, any OpenID Connect provider); ai-os does the sign-in itself;
    - `dev`: every request is `dev_email`. Only on your own machine.

    `pick`, `password`, `code` and `sso` keep the browser signed in with a cookie for
    `session_days`.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    mode: Literal["cloudflare", "jwt", "header", "pick", "password", "code", "sso", "dev"]
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
    create_users: bool = False
    """cloudflare, jwt, header: make a user for an address the proxy vouches for
    and nobody has yet, instead of refusing it. Needs `domains`. (For sso, each
    provider has its own.)"""
    default_role: str = "member"
    """The role such a user gets; it must chat and must not administer."""
    domains: list[str] = []
    """cloudflare, jwt, header with `create_users`: only addresses in these get a user."""
    providers: list[SsoProvider] = []
    """sso: the sign-ins the login page offers."""
    dev_email: str | None = None
    session_days: int = Field(30, ge=1, le=365)
    """pick, password, code, sso: how long a browser stays signed in."""

    @model_validator(mode="after")
    def _complete(self) -> "WebAuthConfig":
        needs = {
            "cloudflare": ["team_domain", "audience"],
            "jwt": ["header", "jwks_url", "issuer", "audience"],
            "header": ["header"],
            "pick": [],
            "password": [],
            "code": [],
            "sso": ["providers"],
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
        self.domains = [d.strip().lstrip("@").casefold() for d in self.domains if d.strip()]
        if self.create_users:
            if self.mode not in PROXIES:
                raise ValueError(
                    f"web.auth create_users is for a login proxy, not {self.mode}"
                    + (" (set it on each provider)" if self.mode == "sso" else "")
                )
            if not self.domains:
                raise ValueError(
                    "web.auth create_users needs domains: otherwise anyone the proxy lets "
                    "through would become a user"
                )
        keys = [p.key for p in self.providers]
        if len(keys) != len(set(keys)):
            raise ValueError("web.auth providers of one kind need an id each")
        return self
