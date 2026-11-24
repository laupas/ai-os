from urllib.parse import parse_qs, quote, urlsplit

from aiohttp import web

from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.oauth_error import OAuthError
from aios.entities.connectors.sign_in_mode import SignInMode
from aios.entities.users.permission import Permission
from aios.web.public_address import PublicAddress
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes

CALLBACK = "/api/oauth/callback"
STATE_COOKIE = "aios_oauth_state"
MINE = "mine"
SHARED = "shared"


class ConnectorAuthRoutes(WebRoutes):
    """Signing a connector in with OAuth, from the console.

    `?account=mine` signs in the caller's own account, for a per-user connector, and
    needs only the right to chat; `?account=shared` signs in the account everybody
    uses, and needs an administrator. Without it, the connector's mode decides.

    The server sends the browser back to `CALLBACK`, which then returns it to the
    Connectors page, saying how it went. That return is a navigation from another
    site, so it cannot carry the console's CSRF header; `WebAuth` lets this one
    path through without it, and the single-use state stands in for it. Only the
    user who started a sign-in can finish it.
    """

    def __init__(
        self, authorizer: ConnectorAuthorizer, catalog: ConnectorCatalog, public_url: str | None
    ) -> None:
        self._authorizer = authorizer
        self._catalog = catalog
        self._public_url = public_url

    def register(self, app: web.Application) -> None:
        app.router.add_post("/api/connectors/{name}/sign-in", self._start)
        app.router.add_delete("/api/connectors/{name}/sign-in", self._sign_out)
        app.router.add_get(CALLBACK, self._callback)
        app.router.add_post(CALLBACK, self._callback)

    async def _start(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.CHAT)
        own = self._own_account(request, caller)
        try:
            url = await self._authorizer.start(
                request.match_info["name"],
                caller.user.id,
                self._redirect_uri(request),
                own,
                caller.user.name,
            )
        except OAuthError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        response = web.json_response({"url": url})
        state = parse_qs(urlsplit(url).query).get("state", [""])[0]
        # Sent back even on a provider's cross-site POST (SameSite=None, which
        # needs Secure), when the session cookie is not.
        response.set_cookie(
            STATE_COOKIE,
            state,
            max_age=600,
            path=CALLBACK,
            httponly=True,
            samesite="None",
            secure=True,
        )
        return response

    async def _sign_out(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.CHAT)
        own = self._own_account(request, caller)
        await self._authorizer.sign_out(request.match_info["name"], caller.user.id if own else None)
        return web.json_response({"ok": True})

    def _own_account(self, request: web.Request, caller: WebCaller) -> bool:
        """Whether the request is about the caller's own account; refuses what the
        caller may not do."""
        connector = self._catalog.get(request.match_info["name"])
        if connector is None:
            raise web.HTTPNotFound(text="no such connector")
        per_user = connector.sign_in is SignInMode.PER_USER
        account = request.query.get("account") or (MINE if per_user else SHARED)
        if account == MINE:
            if not per_user:
                raise web.HTTPBadRequest(text=f"{connector.id} uses one shared account")
            return True
        if account != SHARED:
            raise web.HTTPBadRequest(text="account is mine or shared")
        if not caller.can(Permission.ADMINISTER):
            raise web.HTTPForbidden(text="only an administrator signs in the shared account")
        return False

    async def _callback(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller_if_any(request)
        params = dict(request.query)
        if request.method == "POST":  # response_mode=form_post
            params.update({k: str(v) for k, v in (await request.post()).items()})
        if params.get("error"):
            message = params.get("error_description") or params["error"]
            return self._back(f"sign_in_error={quote(message)}")
        state = params.get("state", "")
        if caller is None and (not state or request.cookies.get(STATE_COOKIE) != state):
            return self._back("sign_in_error=" + quote("this sign-in was started elsewhere"))
        try:
            name = await self._authorizer.finish(
                state,
                params.get("code", ""),
                caller.user.id if caller else None,
                caller.user.name if caller else None,
            )
        except OAuthError as exc:
            return self._back(f"sign_in_error={quote(str(exc))}")
        return self._back(f"signed_in={quote(name)}")

    def _redirect_uri(self, request: web.Request) -> str:
        return PublicAddress(self._public_url).of(request, CALLBACK)

    @staticmethod
    def _back(query: str) -> web.Response:
        raise web.HTTPFound(f"/?{query}#/connectors")
