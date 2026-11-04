import os

from aios.config.web_auth_config import WebAuthConfig
from aios.config.web_config import WebConfig
from aios.web.fixed_identity import FixedIdentity
from aios.web.jwt_header_identity import JwtHeaderIdentity
from aios.web.trusted_header_identity import TrustedHeaderIdentity
from aios.web.web_identity import WebIdentity


class WebIdentityFactory:
    """The identity `web.auth` asks for. The older `access_team_domain` and
    `access_aud` still mean Cloudflare, and `dev_email` still means dev; with none
    of them every request is refused."""

    @staticmethod
    def create(config: WebConfig) -> WebIdentity:
        auth = config.auth
        if auth is None:
            if config.access_team_domain and config.access_aud:
                return JwtHeaderIdentity.cloudflare(config.access_team_domain, config.access_aud)
            return FixedIdentity(config.dev_email)
        return WebIdentityFactory._from(auth)

    @staticmethod
    def _from(auth: WebAuthConfig) -> WebIdentity:
        if auth.mode == "cloudflare":
            return JwtHeaderIdentity.cloudflare(auth.team_domain or "", auth.audience or "")
        if auth.mode == "jwt":
            return JwtHeaderIdentity(
                header=auth.header or "",
                jwks_url=auth.jwks_url or "",
                issuer=auth.issuer or "",
                audience=auth.audience or "",
                email_claim=auth.email_claim,
                algorithms=auth.algorithms,
            )
        if auth.mode == "header":
            secret = os.environ.get(auth.secret_env) if auth.secret_env else None
            if auth.secret_env and not secret:
                raise RuntimeError(f"web.auth.secret_env names {auth.secret_env}, which is not set")
            return TrustedHeaderIdentity(
                header=auth.header or "",
                trusted_proxies=auth.trusted_proxies,
                secret_header=auth.secret_header,
                secret=secret,
            )
        return FixedIdentity(auth.dev_email)
