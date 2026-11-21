import logging
from typing import Any

from aios.entities.users.user import User
from aios.web.login.code_messenger import CodeMessenger
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.login_pending import LoginPending
from aios.web.login.login_refused import LoginRefused
from aios.web.login.login_request import LoginRequest
from aios.web.login.login_throttle import LoginThrottle
from aios.web.login.sign_in_codes import SignInCodes
from aios.web.login.web_login import WebLogin

log = logging.getLogger(__name__)

SENT = "if the name is known, a code is on its way to your chat (Slack, Teams, Signal…)"
TEXT = (
    "Your ai-os sign-in code: {code}\n"
    "It expires in 10 minutes. If you did not just ask for it, ignore this message."
)


class ChatCodeLogin(WebLogin):
    """No password: the user gives their name, ai-os sends a one-time code to one
    of their chat accounts, and the code signs them in. Whoever reads their chat
    can sign in as them."""

    mode = "code"

    def __init__(
        self,
        users: ConsoleUsers,
        codes: SignInCodes,
        messenger: CodeMessenger,
        throttle: LoginThrottle,
    ) -> None:
        self._users = users
        self._codes = codes
        self._messenger = messenger
        self._throttle = throttle

    def page(self) -> dict[str, Any]:
        return {}

    async def sign_in(self, request: LoginRequest) -> User:
        name = (request.username or "").strip()
        if not name:
            raise LoginRefused("give your name or address")
        if self._throttle.blocked(name):
            raise LoginRefused("too many failed attempts; try again in a few minutes")
        user = self._users.named(name)
        if not request.code:
            await self._send(user)
            raise LoginPending(SENT)
        if user is None or not self._codes.use(user.id, request.code):
            self._throttle.failed(name)
            raise LoginRefused("wrong or expired code")
        self._throttle.succeeded(name)
        return user

    async def _send(self, user: User | None) -> None:
        # The same answer whether or not the name is known, unless sending failed.
        if user is None or not self._codes.may_send(user.id):
            return
        code = self._codes.new(user.id)
        via = await self._messenger.send(user, TEXT.format(code=code))
        if via is None:
            raise LoginRefused("could not send a code: no chat account ai-os can reach")
        log.info("web: sign-in code for %s sent on %s", user.name, via)

    def refusal(self, user: User) -> str | None:
        if not self._users.may_sign_in(user):
            return "you have no web account"
        if not self._messenger.reachable(user):
            return (
                "ai-os cannot send you a code: you have no account on an enabled chat "
                "channel (Slack, Teams, Signal, mail)"
            )
        return None
