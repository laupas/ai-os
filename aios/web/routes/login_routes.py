import logging

from aiohttp import web

from aios.web.login.login_pending import LoginPending
from aios.web.login.login_refused import LoginRefused
from aios.web.login.login_request import LoginRequest
from aios.web.login.web_login import WebLogin
from aios.web.login.web_sessions import WebSessions
from aios.web.request_body import RequestBody
from aios.web.web_routes import WebRoutes

log = logging.getLogger(__name__)


class LoginRoutes(WebRoutes):
    """The console's own login page: what it shows, signing in and out. Open to
    anyone when `login` is set (`WebAuth` lets these paths through); behind a
    proxy, `GET /api/login` only tells the page there is no login of its own."""

    def __init__(self, login: WebLogin | None, sessions: WebSessions, days: int) -> None:
        self._login = login
        self._sessions = sessions
        self._days = days

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/login", self._page)
        app.router.add_post("/api/login", self._sign_in)
        app.router.add_post("/api/logout", self._sign_out)

    async def _page(self, request: web.Request) -> web.Response:
        if self._login is None:
            return web.json_response({"mode": None})
        return web.json_response({"mode": self._login.mode, **self._login.page()})

    async def _sign_in(self, request: web.Request) -> web.Response:
        if self._login is None:
            raise web.HTTPNotFound(text="this console has no login of its own")
        body = await RequestBody.parse(request, LoginRequest)
        try:
            user = await self._login.sign_in(body)
        except LoginPending as exc:
            return web.json_response({"ok": False, "pending": True, "detail": str(exc)}, status=202)
        except LoginRefused as exc:
            log.warning("web: refused a sign-in (%s): %s", body.username or body.user_id, exc)
            raise web.HTTPUnauthorized(text=str(exc)) from exc
        log.info("web: %s signed in (%s)", user.name, self._login.mode)
        token = self._sessions.issue(user.id, self._login.mode, self._login.stamp(user), self._days)
        response = web.json_response({"ok": True, "name": user.name})
        WebSessions.set_cookie(request, response, token, self._days)
        return response

    async def _sign_out(self, request: web.Request) -> web.Response:
        response = web.json_response({"ok": True})
        WebSessions.clear_cookie(response)
        return response
