from aiohttp import web

from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.entities.users.web_session import WebSession
from aios.storage.collection import Collection
from aios.web.login.web_sessions import CURRENT, WebSessions
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class SessionRoutes(WebRoutes):
    """The browsers signed in with the console's own login. Everyone sees and ends
    their own; an administrator sees and ends anyone's (`?user=<id>`). Behind a login
    proxy the console has no sessions of its own: the proxy's are the ones to end."""

    def __init__(self, sessions: WebSessions, users: Collection[User], own_login: bool) -> None:
        self._sessions = sessions
        self._users = users
        self._own_login = own_login

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/sessions", self._list)
        app.router.add_delete("/api/sessions/{id}", self._end)
        app.router.add_post("/api/sessions/end-all", self._end_all)

    async def _list(self, request: web.Request) -> web.Response:
        """The signed-in browsers of the caller, or of `?user=` for an administrator."""
        user_id = self._whose(request)
        current = request.get(CURRENT)
        return web.json_response(
            {
                "own_login": self._own_login,
                "sessions": [self._row(s, current) for s in self._sessions.of_user(user_id)],
            }
        )

    async def _end(self, request: web.Request) -> web.Response:
        """Signs one browser out."""
        user_id = self._whose(request)
        if not await self._sessions.end_one(request.match_info["id"], user_id):
            raise web.HTTPNotFound(text="no such session")
        return web.json_response({"ok": True})

    async def _end_all(self, request: web.Request) -> web.Response:
        """Signs every browser out: the caller's others, or all of `?user=`'s."""
        user_id = self._whose(request)
        caller = WebAuth.caller(request)
        keep = request.get(CURRENT) if user_id == caller.user.id else None
        ended = await self._sessions.end_all(user_id, keep=keep)
        return web.json_response({"ended": ended})

    def _whose(self, request: web.Request) -> str:
        caller = WebAuth.caller(request)
        user_id = request.query.get("user") or caller.user.id
        if user_id != caller.user.id:
            WebAuth.caller(request, Permission.ADMINISTER)
            if self._users.get(user_id) is None:
                raise web.HTTPNotFound(text="no such user")
        return user_id

    @staticmethod
    def _row(session: WebSession, current: str | None) -> dict:
        return {
            "id": WebSessions.public_id(session),
            "mode": session.mode,
            "created_at": session.created_at.isoformat(),
            "last_seen_at": session.last_seen_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "user_agent": session.user_agent,
            "address": session.address,
            "current": session.id == current,
        }
