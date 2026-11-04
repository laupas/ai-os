import logging

from aiohttp import web

from aios.config_repo.change_author import ChangeAuthor
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer
from aios.web.web_caller import WebCaller
from aios.web.web_identity import WebIdentity

log = logging.getLogger(__name__)

CHANNEL = "web"
CALLER = web.RequestKey("aios.caller", WebCaller)
CSRF_HEADER = "X-Aios"
# A server sending the browser back after an OAuth sign-in cannot add the header;
# its single-use state is the check there instead.
NO_CSRF_PATHS = frozenset({"/api/oauth/callback"})


class WebAuth:
    """Decides who a request is from and what they may do.

    A request is let in when its email is the `web` account of a user with the
    `chat` permission. Anything that changes state must also carry the `X-Aios`
    header, which a page on another site cannot add without CORS, and this server
    answers no CORS.
    """

    def __init__(
        self, identity: WebIdentity, users: Collection[User], authorizer: Authorizer
    ) -> None:
        self._identity = identity
        self._users = users
        self._authorizer = authorizer

    @web.middleware
    async def middleware(self, request: web.Request, handler):  # type: ignore[no-untyped-def]
        caller = await self._caller(request)
        if caller is None:
            raise web.HTTPForbidden(text="Not allowed. Ask the owner to add your web account.")
        if (
            request.method not in {"GET", "HEAD"}
            and request.path not in NO_CSRF_PATHS
            and request.headers.get(CSRF_HEADER) != "1"
        ):
            raise web.HTTPForbidden(text="missing X-Aios header")
        request[CALLER] = caller
        # Configuration this request changes is committed in the caller's name.
        CurrentAuthor.set(ChangeAuthor(name=caller.user.name, email=caller.account.address))
        return await handler(request)

    @staticmethod
    def caller(request: web.Request, permission: Permission = Permission.CHAT) -> WebCaller:
        caller = request[CALLER]
        if not caller.can(permission):
            raise web.HTTPForbidden(text=f"needs the {permission} permission")
        return caller

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
