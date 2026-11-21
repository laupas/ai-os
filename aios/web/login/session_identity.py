from aiohttp import web

from aios.web.login.console_users import ConsoleUsers
from aios.web.login.web_login import WebLogin
from aios.web.login.web_sessions import WebSessions
from aios.web.web_identity import WebIdentity


class SessionIdentity(WebIdentity):
    """The user a session cookie from the console's own login names, while the
    cookie is valid, was made by the login now in use, and its stamp still holds."""

    def __init__(self, sessions: WebSessions, login: WebLogin, users: ConsoleUsers) -> None:
        self._sessions = sessions
        self._login = login
        self._users = users

    async def email_of(self, request: web.Request) -> str | None:
        claims = self._sessions.read(WebSessions.token_of(request))
        if claims is None or claims.mode != self._login.mode:
            return None
        user = self._users.get(claims.user_id)
        if user is None or claims.stamp != self._login.stamp(user):
            return None
        return ConsoleUsers.address_of(user)
