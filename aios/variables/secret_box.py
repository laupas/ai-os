import base64
import hashlib
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


class SecretBox:
    """Encrypts secret variables at rest.

    The key comes from `AIOS_SECRETS_KEY` when set, which is the point: with the
    key in a secret manager, a copy of the data dir (a backup) holds no readable secret.
    Without it, a key is generated once into the data dir: that still keeps secrets
    out of anything that reads the documents alone, though not out of a copy of the
    whole directory.
    """

    def __init__(self, env_key: str | None, key_file: Path) -> None:
        self._env_key = env_key
        self._key_file = Path(key_file)
        self._fernet: Fernet | None = None

    def encrypt(self, value: str) -> str:
        return self._box().encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str | None:
        """None when the token was made with another key."""
        try:
            return self._box().decrypt(token.encode()).decode()
        except InvalidToken:
            log.error("a secret cannot be decrypted: was AIOS_SECRETS_KEY changed?")
            return None

    def _box(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self._key())
        return self._fernet

    def _key(self) -> bytes:
        if self._env_key:
            return self.key_from(self._env_key)
        if not self._key_file.exists():
            self._key_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self._key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(Fernet.generate_key())
            log.warning(
                "generated %s; set AIOS_SECRETS_KEY to keep the key elsewhere", self._key_file
            )
        return self._key_file.read_bytes().strip()

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
