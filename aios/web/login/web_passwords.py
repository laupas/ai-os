import asyncio
import hashlib

from aios.common.clock import Clock
from aios.entities.users.web_password import WebPassword
from aios.storage.collection import Collection
from aios.web.login.password_hasher import PasswordHasher

MIN_LENGTH = 8


class WebPasswords:
    """The users' console passwords: set, cleared and checked here, and nowhere
    else. Hashing takes a noticeable moment on purpose, so it runs off the loop."""

    def __init__(
        self, passwords: Collection[WebPassword], hasher: PasswordHasher, clock: Clock
    ) -> None:
        self._passwords = passwords
        self._hasher = hasher
        self._clock = clock

    def has(self, user_id: str) -> bool:
        return self._passwords.get(user_id) is not None

    def user_ids(self) -> list[str]:
        return sorted(p.id for p in self._passwords.all())

    async def set(self, user_id: str, password: str, by: str) -> None:
        if len(password) < MIN_LENGTH:
            raise ValueError(f"a password needs at least {MIN_LENGTH} characters")
        hashed = await asyncio.to_thread(self._hasher.hash, password)
        await self._passwords.put(
            WebPassword(id=user_id, hash=hashed, updated_at=self._clock.now(), updated_by=by)
        )

    async def clear(self, user_id: str) -> None:
        await self._passwords.delete(user_id)

    async def verify(self, user_id: str | None, password: str) -> bool:
        stored = self._passwords.get(user_id) if user_id else None
        # Hashed even without a user, so the answer takes as long either way.
        hashed = stored.hash if stored else self._hasher.hash("")
        ok = await asyncio.to_thread(self._hasher.verify, password, hashed)
        return ok and stored is not None

    def stamp(self, user_id: str) -> str:
        """Changes whenever the password does, which ends the sessions made with
        the old one."""
        stored = self._passwords.get(user_id)
        return hashlib.sha256(stored.hash.encode()).hexdigest()[:16] if stored else ""
