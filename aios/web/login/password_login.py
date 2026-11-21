from typing import Any

from aios.entities.users.user import User
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.login_refused import LoginRefused
from aios.web.login.login_request import LoginRequest
from aios.web.login.login_throttle import LoginThrottle
from aios.web.login.web_login import WebLogin
from aios.web.login.web_passwords import WebPasswords

WRONG = "wrong name or password"


class PasswordLogin(WebLogin):
    """A name (the web address, the user's name or an alias) and the password set
    for that user in the console. A changed password ends the user's sessions."""

    mode = "password"

    def __init__(
        self, users: ConsoleUsers, passwords: WebPasswords, throttle: LoginThrottle
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._throttle = throttle

    def page(self) -> dict[str, Any]:
        return {}

    async def sign_in(self, request: LoginRequest) -> User:
        name = (request.username or "").strip()
        if not name or not request.password:
            raise LoginRefused(WRONG)
        if self._throttle.blocked(name):
            raise LoginRefused("too many failed attempts; try again in a few minutes")
        user = self._users.named(name)
        ok = await self._passwords.verify(user.id if user else None, request.password)
        if user is None or not ok:
            self._throttle.failed(name)
            raise LoginRefused(WRONG)
        self._throttle.succeeded(name)
        return user

    def stamp(self, user: User) -> str:
        return self._passwords.stamp(user.id)

    def refusal(self, user: User) -> str | None:
        if not self._users.may_sign_in(user):
            return "you have no web account"
        if not self._passwords.has(user.id):
            return "you have no password yet: set one under Settings → People first"
        return None
