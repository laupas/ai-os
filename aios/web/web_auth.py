import logging

from aiohttp import web

from aios.config_repo.change_author import ChangeAuthor
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer
from aios.web.login.new_user_policy import NewUserPolicy
from aios.web.web_caller import WebCaller
from aios.web.web_identity import WebIdentity

log = logging.getLogger(__name__)

CHANNEL = "web"
CALLER = web.RequestKey("aios.caller", WebCaller)
CSRF_HEADER = "X-Aios"
# A server sending the browser back after an OAuth sign-in cannot add the header;
# its single-use state is the check there instead.
NO_CSRF_PATHS = frozenset({"/api/oauth/callback"})
# With the console's own login, what a browser needs before signing in.
LOGIN_PATHS = frozenset({"/", "/api/login", "/api/logout"})
LOGIN_PREFIXES = ("/static/", "/api/login/sso/")
# A connector's OAuth sign-in coming back. A provider answering with a cross-site
# POST (form_post) arrives without the session cookie (SameSite=Lax); the route
# then proves the browser with a state cookie of its own instead.
OPTIONAL_PATHS = frozenset({"/api/oauth/callback"})
# Called by programs, not people: each route checks its own token.
HOOK_PREFIXES = ("/hooks/",)


class WebAuth:
    """Decides who a request is from and what they may do.

    A request is let in when its email is the `web` account of a user with the
    `chat` permission. Anything that changes state must also carry the `X-Aios`
    header, which a page on another site cannot add without CORS, and this server
    answers no CORS.

    Behind a proxy with `create_users`, `new_users` makes a user for an address
    nobody has yet (see `NewUserPolicy`).

    With `login_page` (the console's own login), the page, its scripts and the
    login routes are served to anyone, so a browser can sign in.

    `/hooks/` is let through without an identity: those routes prove the caller
    with a token of their own, and have no session a CSRF check could protect.
    """

    def __init__(
        self,
        identity: WebIdentity,
        users: Collection[User],
        authorizer: Authorizer,
        login_page: bool = False,
        new_users: NewUserPolicy | None = None,
    ) -> None:
        self._identity = identity
        self._users = users
        self._authorizer = authorizer
        self._login_page = login_page
        self._new_users = new_users

    @web.middleware
    async def middleware(self, request: web.Request, handler):  # type: ignore[no-untyped-def]
        if request.path.startswith(HOOK_PREFIXES):
            return await handler(request)
        if self._login_page and self._open(request.path):
            self._check_csrf(request)
            return await handler(request)
        caller = await self._caller(request)
        if caller is None and request.path in OPTIONAL_PATHS:
            return await handler(request)
        if caller is None:
            raise web.HTTPForbidden(text="Not allowed. Ask the owner to add your web account.")
        self._check_csrf(request)
        request[CALLER] = caller
        # Configuration this request changes is committed in the caller's name.
        CurrentAuthor.set(ChangeAuthor(name=caller.user.name, email=caller.account.address))
        return await handler(request)

    @staticmethod
    def caller_if_any(request: web.Request) -> WebCaller | None:
        """The caller on a route in `OPTIONAL_PATHS`, which may have none."""
        return request.get(CALLER)

    @staticmethod
    def caller(request: web.Request, permission: Permission = Permission.CHAT) -> WebCaller:
        caller = request[CALLER]
        if not caller.can(permission):
            raise web.HTTPForbidden(text=f"needs the {permission} permission")
        return caller

    @staticmethod
    def _open(path: str) -> bool:
        return path in LOGIN_PATHS or path.startswith(LOGIN_PREFIXES)

    @staticmethod
    def _check_csrf(request: web.Request) -> None:
        if (
            request.method not in {"GET", "HEAD"}
            and request.path not in NO_CSRF_PATHS
            and request.headers.get(CSRF_HEADER) != "1"
        ):
            raise web.HTTPForbidden(text="missing X-Aios header")

    async def _caller(self, request: web.Request) -> WebCaller | None:
        email = await self._identity.email_of(request)
        if email is None:
            return None
        wanted = email.casefold()
        user = self._users.find(
            lambda u: any(
                a.channel == CHANNEL and a.address.casefold() == wanted for a in u.accounts
            )
        )
        if user is None and self._new_users is not None:
            user = await self._new_users.user_for(email)
        if user is None or not self._authorizer.has(user, Permission.CHAT):
            log.warning("web: refused %s", email)
            return None
        account = next(
            a for a in user.accounts if a.channel == CHANNEL and a.address.casefold() == wanted
        )
        return WebCaller(
            user=user,
            account=ChannelAccount(channel=CHANNEL, address=account.address),
            permissions=self._authorizer.permissions_of(user),
        )
