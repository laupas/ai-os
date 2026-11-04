from urllib.parse import quote

from aiohttp import web

from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.oauth_error import OAuthError
from aios.entities.users.permission import Permission
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

CALLBACK = "/api/oauth/callback"


class ConnectorAuthRoutes(WebRoutes):
    """Signing a connector in with OAuth, from the console. Administrators only.

    The server sends the browser back to `CALLBACK`, which then returns it to the
    Connectors page, saying how it went. That return is a navigation from another
    site, so it cannot carry the console's CSRF header; `WebAuth` lets this one
    path through without it, and the single-use state stands in for it.
    """

    def __init__(self, authorizer: ConnectorAuthorizer, public_url: str | None) -> None:
        self._authorizer = authorizer
        self._public_url = public_url

    def register(self, app: web.Application) -> None:
        app.router.add_post("/api/connectors/{name}/sign-in", self._start)
        app.router.add_delete("/api/connectors/{name}/sign-in", self._sign_out)
        app.router.add_get(CALLBACK, self._callback)
        app.router.add_post(CALLBACK, self._callback)

    async def _start(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        try:
            url = await self._authorizer.start(
                request.match_info["name"], caller.user.id, self._redirect_uri(request)
            )
        except OAuthError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return web.json_response({"url": url})

    async def _sign_out(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._authorizer.sign_out(request.match_info["name"])
        return web.json_response({"ok": True})

    async def _callback(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        params = dict(request.query)
        if request.method == "POST":  # response_mode=form_post
            params.update({k: str(v) for k, v in (await request.post()).items()})
        if params.get("error"):
            message = params.get("error_description") or params["error"]
            return self._back(f"sign_in_error={quote(message)}")
        try:
            name = await self._authorizer.finish(
                params.get("state", ""), params.get("code", ""), caller.user.id, caller.user.name
            )
        except OAuthError as exc:
            return self._back(f"sign_in_error={quote(str(exc))}")
        return self._back(f"signed_in={quote(name)}")

    def _redirect_uri(self, request: web.Request) -> str:
        if self._public_url:
            return self._public_url.rstrip("/") + CALLBACK
        # Behind the tunnel the hop to ai-os is plain http, so the scheme the
        # browser used is not on the request; a public host is always https.
        host = request.host
        local = host.split(":")[0] in {"localhost", "127.0.0.1"}
        return f"{'http' if local else 'https'}://{host}{CALLBACK}"

    @staticmethod
    def _back(query: str) -> web.Response:
        raise web.HTTPFound(f"/?{query}#/connectors")
