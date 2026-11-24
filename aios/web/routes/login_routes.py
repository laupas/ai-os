import logging
from urllib.parse import quote

from aiohttp import web

from aios.web.login.login_pending import LoginPending
from aios.web.login.login_refused import LoginRefused
from aios.web.login.login_request import LoginRequest
from aios.web.login.redirect_login import RedirectLogin
from aios.web.login.web_login import WebLogin
from aios.web.login.web_sessions import WebSessions
from aios.web.public_address import PublicAddress
from aios.web.request_body import RequestBody
from aios.web.web_routes import WebRoutes

log = logging.getLogger(__name__)

SSO = "/api/login/sso/"
CALLBACK = SSO + "callback"
STATE_COOKIE = "aios_sso_state"


class LoginRoutes(WebRoutes):
    """The console's own login page: what it shows, signing in and out. Open to
    anyone when `login` is set (`WebAuth` lets these paths through); behind a
    proxy, `GET /api/login` only tells the page there is no login of its own.

    A `RedirectLogin` (single sign-on) also gets `/api/login/sso/start/<provider>`,
    which sends the browser to the provider, and the callback it comes back to. The
    `state` is also kept in a cookie of this browser, so a sign-in started in one
    browser cannot be finished in another (login CSRF)."""

    def __init__(
        self,
        login: WebLogin | None,
        sessions: WebSessions,
        days: int,
        public_url: str | None = None,
    ) -> None:
        self._login = login
        self._sessions = sessions
        self._days = days
        self._address = PublicAddress(public_url)

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/login", self._page)
        app.router.add_post("/api/login", self._sign_in)
        app.router.add_post("/api/logout", self._sign_out)
        app.router.add_get(SSO + "start/{provider}", self._start)
        app.router.add_get(CALLBACK, self._callback)

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
        WebSessions.set_cookie(response, token, self._days, self._address.secure(request))
        return response

    async def _sign_out(self, request: web.Request) -> web.Response:
        response = web.json_response({"ok": True})
        WebSessions.clear_cookie(response)
        return response

    async def _start(self, request: web.Request) -> web.Response:
        login = self._redirect_login()
        try:
            url, state = await login.start(
                request.match_info["provider"], self._address.of(request, CALLBACK)
            )
        except LoginRefused as exc:
            return self._back(str(exc))
        response = web.HTTPFound(url)
        response.set_cookie(
            STATE_COOKIE,
            state,
            max_age=600,
            path=SSO,
            httponly=True,
            samesite="Lax",
            secure=self._address.secure(request),
        )
        raise response

    async def _callback(self, request: web.Request) -> web.Response:
        login = self._redirect_login()
        params = request.query
        if params.get("error"):
            return self._back(params.get("error_description") or params["error"])
        state = params.get("state", "")
        if not state or request.cookies.get(STATE_COOKIE) != state:
            return self._back("this sign-in was started in another browser; start again")
        try:
            user = await login.finish(state, params.get("code", ""))
        except LoginRefused as exc:
            log.warning("web: refused a single sign-on: %s", exc)
            return self._back(str(exc))
        log.info("web: %s signed in (%s)", user.name, login.mode)
        token = self._sessions.issue(user.id, login.mode, login.stamp(user), self._days)
        response = web.HTTPFound("/")
        WebSessions.set_cookie(response, token, self._days, self._address.secure(request))
        response.del_cookie(STATE_COOKIE, path=SSO)
        raise response

    def _redirect_login(self) -> RedirectLogin:
        if not isinstance(self._login, RedirectLogin):
            raise web.HTTPNotFound(text="this console has no single sign-on")
        return self._login

    @staticmethod
    def _back(message: str) -> web.Response:
        response = web.HTTPFound(f"/?login_error={quote(message)}")
        response.del_cookie(STATE_COOKIE, path=SSO)
        raise response
