import os

from aios.config.web_auth_config import WebAuthConfig
from aios.config.web_config import WebConfig
from aios.web.fixed_identity import FixedIdentity
from aios.web.jwt_header_identity import JwtHeaderIdentity
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.session_identity import SessionIdentity
from aios.web.login.web_login import WebLogin
from aios.web.login.web_sessions import WebSessions
from aios.web.trusted_header_identity import TrustedHeaderIdentity
from aios.web.web_identity import WebIdentity


class WebIdentityFactory:
    """The identity `web.auth` asks for (see `WebConfig.effective_auth`: nothing set
    means `pick`). A mode in `logins` is the console's own login page, remembered
    with a session cookie."""

    def __init__(self, sessions: WebSessions, users: ConsoleUsers, logins: list[WebLogin]) -> None:
        self._sessions = sessions
        self._users = users
        self._logins = {login.mode: login for login in logins}

    def create(self, config: WebConfig) -> WebIdentity:
        return self.from_auth(config.effective_auth())

    def login_for(self, auth: WebAuthConfig | None) -> WebLogin | None:
        """The login page `auth` asks for; None for a proxy or dev."""
        login = self._logins.get(auth.mode) if auth is not None else None
        return login.configured(auth) if login is not None and auth is not None else None

    def from_auth(self, auth: WebAuthConfig) -> WebIdentity:
        """Also how the console tries a new `web.auth` on its own request before
        saving it."""
        login = self.login_for(auth)
        if login is not None:
            return SessionIdentity(self._sessions, login, self._users)
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
