import hmac
import secrets
from datetime import timedelta

from aios.common.clock import Clock
from aios.web.login.pending_code import PendingCode


class SignInCodes:
    """One-time codes for the chat-code login, kept in memory: a restart forgets
    them, which only means asking for a new one. A code expires after `lifetime`,
    works once, and is dropped after `tries` wrong guesses."""

    def __init__(
        self,
        clock: Clock,
        lifetime: timedelta = timedelta(minutes=10),
        tries: int = 5,
        resend_after: timedelta = timedelta(seconds=60),
    ) -> None:
        self._clock = clock
        self._lifetime = lifetime
        self._tries = tries
        self._resend_after = resend_after
        self._codes: dict[str, PendingCode] = {}

    def may_send(self, user_id: str) -> bool:
        """False while a code sent moments ago is still valid, so the login page
        cannot be used to flood someone's chat."""
        pending = self._valid(user_id)
        return pending is None or self._clock.now() - pending.sent >= self._resend_after

    def new(self, user_id: str) -> str:
        now = self._clock.now()
        code = f"{secrets.randbelow(10**6):06d}"
        self._codes[user_id] = PendingCode(code=code, expires=now + self._lifetime, sent=now)
        return code

    def use(self, user_id: str, code: str) -> bool:
        pending = self._valid(user_id)
        if pending is None:
            return False
        if hmac.compare_digest(pending.code, code.strip()):
            del self._codes[user_id]
            return True
        pending.tries += 1
        if pending.tries >= self._tries:
            del self._codes[user_id]
        return False

    def _valid(self, user_id: str) -> PendingCode | None:
        pending = self._codes.get(user_id)
        if pending is not None and pending.expires <= self._clock.now():
            del self._codes[user_id]
            return None
        return pending
