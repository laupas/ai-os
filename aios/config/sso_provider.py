import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MICROSOFT = "https://login.microsoftonline.com/{tenant}/v2.0"
GOOGLE = "https://accounts.google.com"
LABELS = {"microsoft": "Microsoft", "google": "Google", "oidc": "single sign-on"}
# Accounts of any organisation: their address is not checked by anyone ai-os trusts.
SHARED_TENANTS = frozenset({"common", "organizations"})
LOCAL = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?(/|$)")


class SsoProvider(BaseModel):
    """One button on the login page: an OpenID Connect sign-in at Microsoft (Entra
    ID, Microsoft 365), Google, or any other OpenID provider (`oidc`). The user is
    the one whose `web` account is the address the provider vouches for.

    The client secret is never here (aios.yaml is in git): `client_secret_variable`
    names the Variable, or environment variable, that holds it."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    kind: Literal["microsoft", "google", "oidc"]
    id: str | None = Field(None, pattern=r"^[a-z0-9-]+$")
    """In the sign-in address; default: `kind`. Needed only for two of one kind."""
    label: str | None = None
    """On the button, after "Sign in with"; default: Microsoft, Google, single sign-on."""
    client_id: str
    client_secret_variable: str | None = Field(None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    """None for a public client (PKCE only); Microsoft and Google need a secret."""
    tenant: str | None = None
    """microsoft: the directory (tenant) id or a domain of it, or `consumers` for
    personal Microsoft accounts."""
    issuer: str | None = None
    """oidc: e.g. https://auth.example.com/application/o/ai-os/"""
    domains: list[str] = []
    """Only addresses in these domains get in; empty: any the provider vouches for."""
    create_users: bool = False
    """Make a user on the first sign-in of an address nobody has yet, instead of
    refusing it. Needs `domains`, unless a Microsoft tenant of your own bounds who
    can sign in at all."""
    default_role: str = "member"
    """The role a user made by `create_users` gets. It must let them chat and must
    not administer: whoever the provider vouches for is not made an administrator."""
    email_claim: str = "email"
    scopes: list[str] = ["openid", "email", "profile"]

    @property
    def key(self) -> str:
        return self.id or self.kind

    @property
    def name(self) -> str:
        return self.label or LABELS[self.kind]

    def issuer_url(self) -> str:
        if self.kind == "microsoft":
            return MICROSOFT.format(tenant=self.tenant)
        if self.kind == "google":
            return GOOGLE
        return (self.issuer or "").rstrip("/")

    @model_validator(mode="after")
    def _complete(self) -> "SsoProvider":
        self.domains = [d.strip().lstrip("@").casefold() for d in self.domains if d.strip()]
        if self.kind == "microsoft":
            if not self.tenant:
                raise ValueError("a microsoft sign-in needs tenant (your directory id or domain)")
            if self.tenant.casefold() in SHARED_TENANTS:
                raise ValueError(
                    f"tenant {self.tenant} lets in accounts of any organisation, whose addresses "
                    "nobody checks; use your own tenant id or domain, or consumers"
                )
        if self.kind in ("microsoft", "google") and not self.client_secret_variable:
            raise ValueError(f"a {self.kind} sign-in needs client_secret_variable")
        if self.kind == "oidc":
            if not self.issuer:
                raise ValueError("an oidc sign-in needs issuer")
            if not (self.issuer.startswith("https://") or LOCAL.match(self.issuer)):
                raise ValueError("the issuer must be an https address")
        own_tenant = self.kind == "microsoft" and (self.tenant or "").casefold() != "consumers"
        if self.create_users and not self.domains and not own_tenant:
            raise ValueError(
                "create_users needs domains: otherwise anyone with an account at the "
                "provider would become a user"
            )
        if "openid" not in self.scopes:
            raise ValueError("scopes must include openid")
        return self
