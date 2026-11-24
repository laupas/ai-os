from aiohttp import web

from aios.web.login.console_users import ConsoleUsers
from aios.web.login.web_login import WebLogin
from aios.web.login.web_sessions import CURRENT, WebSessions
from aios.web.web_identity import WebIdentity


class SessionIdentity(WebIdentity):
    """The user a live session of the console's own login names, while it was made
    by the login now in use and its stamp still holds."""

    def __init__(self, sessions: WebSessions, login: WebLogin, users: ConsoleUsers) -> None:
        self._sessions = sessions
        self._login = login
        self._users = users

    async def email_of(self, request: web.Request) -> str | None:
        session = self._sessions.read(WebSessions.token_of(request))
        if session is None or session.mode != self._login.mode:
            return None
        user = self._users.get(session.user_id)
        if user is None or session.stamp != self._login.stamp(user):
            return None
        await self._sessions.touch(session)
        request[CURRENT] = session.id
        return ConsoleUsers.address_of(user)
