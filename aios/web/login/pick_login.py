from typing import Any

from aios.entities.users.user import User
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.login_refused import LoginRefused
from aios.web.login.login_request import LoginRequest
from aios.web.login.web_login import WebLogin


class PickLogin(WebLogin):
    """No password: the login page lists the console's users and whoever opens it
    picks one. Proves nothing about who is at the browser, so only for a network
    where everyone is trusted."""

    mode = "pick"

    def __init__(self, users: ConsoleUsers) -> None:
        self._users = users

    def page(self) -> dict[str, Any]:
        return {"users": [{"id": u.id, "name": u.name} for u in self._users.all()]}

    async def sign_in(self, request: LoginRequest) -> User:
        user = self._users.get(request.user_id or "")
        if user is None:
            raise LoginRefused("no such user")
        return user

    def refusal(self, user: User) -> str | None:
        return None if self._users.may_sign_in(user) else "you have no web account"
