from abc import ABC, abstractmethod
from typing import Any

from aios.config.web_auth_config import WebAuthConfig
from aios.entities.users.user import User
from aios.web.login.login_request import LoginRequest


class WebLogin(ABC):
    """One way of signing in on the console's own login page. A new way is a class
    here plus an entry in `WebIdentityFactory`'s logins; the session cookie,
    the login page's routes and the lockout check come with it."""

    mode: str

    def configured(self, auth: WebAuthConfig) -> "WebLogin":
        """This login with the settings `auth` gives it (SSO's providers)."""
        return self

    @abstractmethod
    def page(self) -> dict[str, Any]:
        """What the login page needs to show, sent to anyone who opens it."""

    @abstractmethod
    async def sign_in(self, request: LoginRequest) -> User:
        """The user `request` signs in, or `LoginRefused`."""

    def stamp(self, user: User) -> str:
        """Part of every session cookie; when it changes, the user's sessions end."""
        return ""

    @abstractmethod
    def refusal(self, user: User) -> str | None:
        """Why `user` could not sign in this way, or None when they could. Settings
        refuse to switch to a login that would lock out the administrator saving it."""

    async def problem(self) -> str | None:
        """Why this login would not work for anyone (an unset secret, an unreachable
        provider), or None; checked before Settings switch to it."""
        return None
