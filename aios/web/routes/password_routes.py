from aiohttp import web

from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer
from aios.web.login.web_passwords import WebPasswords
from aios.web.password_request import PasswordRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes


class PasswordRoutes(WebRoutes):
    """Passwords for the console's own login. Anyone may change their own (with the
    current one, if they have one); `manage_users` sets and clears other people's,
    and an administrator's only by another administrator. The hash never leaves
    ai-os: the console learns only who has a password."""

    def __init__(
        self, passwords: WebPasswords, users: Collection[User], authorizer: Authorizer
    ) -> None:
        self._passwords = passwords
        self._users = users
        self._authorizer = authorizer

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/passwords", self._list)
        app.router.add_put("/api/me/password", self._set_own)
        app.router.add_put("/api/passwords/{id}", self._set)
        app.router.add_delete("/api/passwords/{id}", self._clear)

    async def _list(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        mine = self._passwords.has(caller.user.id)
        if not caller.can(Permission.MANAGE_USERS):
            return web.json_response({"mine": mine, "users": None})
        return web.json_response({"mine": mine, "users": self._passwords.user_ids()})

    async def _set_own(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        body = await RequestBody.parse(request, PasswordRequest)
        user_id = caller.user.id
        if self._passwords.has(user_id) and not await self._passwords.verify(
            user_id, body.current or ""
        ):
            raise web.HTTPForbidden(text="the current password is wrong")
        await self._store(user_id, body.password, caller)
        return web.json_response({"ok": True})

    async def _set(self, request: web.Request) -> web.Response:
        caller, user = self._target(request)
        body = await RequestBody.parse(request, PasswordRequest)
        await self._store(user.id, body.password, caller)
        return web.json_response({"ok": True})

    async def _clear(self, request: web.Request) -> web.Response:
        _, user = self._target(request)
        await self._passwords.clear(user.id)
        return web.json_response({"ok": True})

    def _target(self, request: web.Request) -> tuple[WebCaller, User]:
        caller = WebAuth.caller(request, Permission.MANAGE_USERS)
        user = self._users.get(request.match_info["id"])
        if user is None:
            raise web.HTTPNotFound(text="no such user")
        if self._authorizer.has(user, Permission.ADMINISTER) and not caller.can(
            Permission.ADMINISTER
        ):
            raise web.HTTPForbidden(text="only an administrator sets an administrator's password")
        return caller, user

    async def _store(self, user_id: str, password: str, caller: WebCaller) -> None:
        try:
            await self._passwords.set(user_id, password, caller.account.address)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
