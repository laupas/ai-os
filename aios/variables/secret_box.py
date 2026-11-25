import base64
import hashlib
import hmac
import logging
from collections.abc import Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

log = logging.getLogger(__name__)


class SecretBox:
    """Encrypts secrets at rest with the key from `AIOS_SECRETS_KEY` (`SecretsKeySource`).

    Encrypts with `key` only and decrypts with it or any of `previous`: while a key is
    being replaced, everything stays readable, and `rekey` moves each secret over.
    """

    def __init__(self, key: str, previous: Sequence[str] = ()) -> None:
        self._key = self.key_from(key)
        self._current = Fernet(self._key)
        self._previous_keys = [self.key_from(k) for k in previous]
        self._previous = [Fernet(k) for k in self._previous_keys]
        self._all = MultiFernet([self._current, *self._previous])
        self._previous_fingerprints = [self.fingerprint_of(k) for k in previous]

    def encrypt(self, value: str) -> str:
        return self._current.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str | None:
        """None when no key in use or previous opens it."""
        try:
            return self._all.decrypt(token.encode()).decode()
        except InvalidToken:
            log.error("a secret cannot be decrypted: was AIOS_SECRETS_KEY changed?")
            return None

    def is_current(self, token: str) -> bool:
        """Whether the key in use opens it; False also when nothing does."""
        try:
            self._current.decrypt(token.encode())
            return True
        except InvalidToken:
            return False

    def rekey(self, token: str) -> str | None:
        """The same secret encrypted with the key in use: `token` itself when it is on
        that key already, None when no key opens it."""
        if self.is_current(token):
            return token
        try:
            return self._all.rotate(token.encode()).decode()
        except InvalidToken:
            return None

    def fingerprint(self) -> str:
        return self.fingerprint_of(self._key.decode())

    def previous_fingerprints(self) -> list[str]:
        return list(self._previous_fingerprints)

    def derive_key(self, purpose: str) -> bytes:
        """A key for `purpose` (signing the console's sessions, say), derived from
        this box's key, so it needs no file or setting of its own."""
        return hmac.new(self._key, purpose.encode(), hashlib.sha256).digest()

    def derive_keys(self, purpose: str) -> list[bytes]:
        """`derive_key` from the key in use, then from each previous key: to open what
        was sealed before the key was replaced (a backup)."""
        return [
            hmac.new(k, purpose.encode(), hashlib.sha256).digest()
            for k in [self._key, *self._previous_keys]
        ]

    @classmethod
    def fingerprint_of(cls, key: str) -> str:
        """A short name for a key, safe to show: two keys with the same fingerprint are
        the same key, and nothing about the key can be learnt from it."""
        digest = hmac.new(cls.key_from(key), b"aios key fingerprint", hashlib.sha256).hexdigest()
        return f"{digest[:4]} {digest[4:8]}"

    @staticmethod
    def new_key() -> str:
        return Fernet.generate_key().decode()

    @staticmethod
    def key_from(value: str) -> bytes:
        """A Fernet key as is; any other value, such as a long password generated in
        a secret manager, is hashed into one. Hashing is enough for a generated password,
        which has the entropy a key needs; it is not a way to make a short one safe."""
        try:
            if len(base64.urlsafe_b64decode(value.encode())) == 32:
                return value.encode()
        except ValueError:
            pass
        return base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest())
