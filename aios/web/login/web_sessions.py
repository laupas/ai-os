import hashlib
import secrets
from datetime import timedelta

from aiohttp import web

from aios.common.clock import Clock
from aios.entities.users.web_session import WebSession
from aios.storage.collection import Collection

COOKIE = "aios_session"
CURRENT = web.RequestKey("aios.session", str)
"""The session id of the request, once `SessionIdentity` recognised it."""
TOUCH_EVERY = timedelta(minutes=5)
PUBLIC_ID = 16


class WebSessions:
    """The browsers signed in with the console's own login, kept on the server so
    each can be ended: signing out ends this one, an administrator or the user can
    end any or all of theirs, and a new password or a deleted user ends them too.

    The cookie holds a random token; only its hash is stored. A session ends at
    `expires_at`, after `idle_minutes` without a request, when its mode is no longer
    the login in use, or when its stamp no longer holds."""

    def __init__(self, sessions: Collection[WebSession], clock: Clock) -> None:
        self._sessions = sessions
        self._clock = clock

    async def issue(
        self,
        user_id: str,
        mode: str,
        stamp: str,
        days: int,
        request: web.Request | None = None,
        idle_minutes: int | None = None,
    ) -> str:
        await self._prune()
        token = secrets.token_urlsafe(32)
        now = self._clock.now()
        await self._sessions.put(
            WebSession(
                id=self._hash(token),
                user_id=user_id,
                mode=mode,
                stamp=stamp,
                created_at=now,
                expires_at=now + timedelta(days=days),
                last_seen_at=now,
                idle_minutes=idle_minutes,
                user_agent=(request.headers.get("User-Agent", "")[:300] if request else ""),
                address=self._address(request) if request else "",
            )
        )
        return token

    def read(self, token: str | None) -> WebSession | None:
        """The live session `token` names; None for anything else."""
        if not token:
            return None
        session = self._sessions.get(self._hash(token))
        return session if session is not None and self._alive(session) else None

    async def touch(self, session: WebSession) -> None:
        """Notes a request, at most every few minutes, for the idle limit and the list."""
        now = self._clock.now()
        if now - session.last_seen_at >= TOUCH_EVERY:
            await self._sessions.put(session.model_copy(update={"last_seen_at": now}))

    def of_user(self, user_id: str) -> list[WebSession]:
        return sorted(
            (s for s in self._sessions.all() if s.user_id == user_id and self._alive(s)),
            key=lambda s: s.last_seen_at,
            reverse=True,
        )

    async def end(self, token: str | None) -> None:
        if token:
            await self._sessions.delete(self._hash(token))

    async def end_one(self, public_id: str, user_id: str) -> bool:
        """Ends `user_id`'s session with this public id; False if there is none."""
        found = next((s for s in self.of_user(user_id) if self.public_id(s) == public_id), None)
        if found is None:
            return False
        await self._sessions.delete(found.id)
        return True

    async def end_all(self, user_id: str, keep: str | None = None) -> int:
        """Ends every session of `user_id` but `keep` (a session id); returns how many."""
        ended = [s for s in self._sessions.all() if s.user_id == user_id and s.id != keep]
        for session in ended:
            await self._sessions.delete(session.id)
        return len(ended)

    @staticmethod
    def public_id(session: WebSession) -> str:
        """What the console shows and sends back: part of the hash, never the token."""
        return session.id[:PUBLIC_ID]

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

    def _alive(self, session: WebSession) -> bool:
        now = self._clock.now()
        if session.expires_at <= now:
            return False
        idle = session.idle_minutes
        return idle is None or now - session.last_seen_at < timedelta(minutes=idle)

    async def _prune(self) -> None:
        for session in self._sessions.all():
            if not self._alive(session):
                await self._sessions.delete(session.id)

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _address(request: web.Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return (forwarded or request.remote or "")[:64]
