import base64
import hashlib
import hmac
import os


class PasswordHasher:
    """Hashes console passwords with scrypt from the standard library. The stored
    form names its parameters, so they can be raised later without breaking the
    hashes already stored."""

    N = 2**15
    R = 8
    P = 1
    MAX_MEMORY = 64 * 1024**2

    def hash(self, password: str) -> str:
        salt = os.urandom(16)
        digest = self._scrypt(password, salt, self.N, self.R, self.P)
        return f"scrypt${self.N}${self.R}${self.P}${self._b64(salt)}${self._b64(digest)}"

    def verify(self, password: str, stored: str) -> bool:
        try:
            scheme, n, r, p, salt, digest = stored.split("$")
            if scheme != "scrypt":
                return False
            expected = base64.urlsafe_b64decode(digest)
            actual = self._scrypt(password, base64.urlsafe_b64decode(salt), int(n), int(r), int(p))
        except ValueError:
            return False
        return hmac.compare_digest(actual, expected)

    def _scrypt(self, password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        return hashlib.scrypt(
            password.encode(), salt=salt, n=n, r=r, p=p, maxmem=self.MAX_MEMORY, dklen=32
        )

    @staticmethod
    def _b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode()
