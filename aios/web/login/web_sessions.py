import base64
import hashlib
import hmac
import json
from datetime import timedelta

from aiohttp import web
from pydantic import ValidationError

from aios.common.clock import Clock
from aios.web.login.session_claims import SessionClaims

COOKIE = "aios_session"


class WebSessions:
    """The cookie that keeps a browser signed in after the console's own login.

    It holds the user's id, the login mode and a stamp from that login (see
    `WebLogin.stamp`), signed with a key derived from the secrets key. Nothing is
    kept on the server: a session ends when it expires, when the mode changes, or
    when the stamp does (a new password).
    """

    def __init__(self, key: bytes, clock: Clock) -> None:
        self._key = key
        self._clock = clock

    def issue(self, user_id: str, mode: str, stamp: str, days: int) -> str:
        expires = self._clock.now() + timedelta(days=days)
        claims = SessionClaims(user_id=user_id, mode=mode, stamp=stamp, expires=expires.timestamp())
        payload = base64.urlsafe_b64encode(claims.model_dump_json().encode()).decode()
        return f"{payload}.{self._sign(payload)}"

    def read(self, token: str | None) -> SessionClaims | None:
        """The claims of a valid, unexpired token; None for anything else."""
        if not token or "." not in token:
            return None
        payload, signature = token.rsplit(".", 1)
        if not hmac.compare_digest(signature, self._sign(payload)):
            return None
        try:
            claims = SessionClaims.model_validate(json.loads(base64.urlsafe_b64decode(payload)))
        except (ValueError, ValidationError):
            return None
        return claims if claims.expires > self._clock.now().timestamp() else None

    @staticmethod
    def token_of(request: web.Request) -> str | None:
        return request.cookies.get(COOKIE)

    @staticmethod
    def set_cookie(response: web.Response, token: str, days: int, secure: bool) -> None:
        response.set_cookie(
            COOKIE,
            token,
            max_age=days * 86400,
            path="/",
            httponly=True,
            samesite="Lax",
            secure=secure,
        )

    @staticmethod
    def clear_cookie(response: web.Response) -> None:
        response.del_cookie(COOKIE, path="/")

    def _sign(self, payload: str) -> str:
        digest = hmac.new(self._key, payload.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode()
