import secrets
from datetime import timedelta

from aios.common.clock import Clock
from aios.web.login.sso.sso_attempt import SsoAttempt

LIMIT = 1000


class SsoAttempts:
    """Sign-ins under way, by their `state`, kept in memory: a restart only means
    clicking the button again. Each is taken once and expires after `lifetime`."""

    def __init__(self, clock: Clock, lifetime: timedelta = timedelta(minutes=10)) -> None:
        self._clock = clock
        self._lifetime = lifetime
        self._open: dict[str, SsoAttempt] = {}

    def open(self, provider: str, redirect_uri: str) -> tuple[str, SsoAttempt]:
        now = self._clock.now()
        self._open = {k: a for k, a in self._open.items() if a.expires > now}
        if len(self._open) >= LIMIT:
            self._open.pop(next(iter(self._open)))
        state = secrets.token_urlsafe(32)
        attempt = SsoAttempt(
            provider=provider,
            nonce=secrets.token_urlsafe(32),
            verifier=secrets.token_urlsafe(48),
            redirect_uri=redirect_uri,
            expires=now + self._lifetime,
        )
        self._open[state] = attempt
        return state, attempt

    def take(self, state: str) -> SsoAttempt | None:
        attempt = self._open.pop(state, None)
        if attempt is None or attempt.expires <= self._clock.now():
            return None
        return attempt
