import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from aios.backup.backup_header import BackupHeader
from aios.backup.backup_unreadable import BackupUnreadable
from aios.variables.secret_box import SecretBox

MAGIC = b"AIOS-BACKUP\n"
PURPOSE = "backup"


class BackupCipher:
    """Seals an archive with AES-GCM under a key derived from the secrets key, so a
    backup is as safe as the stored secrets are, and needs no password of its own.

    The file: `MAGIC`, the header as one line of JSON (readable: which key opens it),
    a 12-byte nonce, then the ciphertext. The header is authenticated with the rest."""

    def __init__(self, box: SecretBox) -> None:
        self._box = box

    def fingerprint(self) -> str:
        """The secrets key's fingerprint: the key a backup sealed now needs."""
        return self._box.fingerprint()

    def seal(self, header: BackupHeader, archive: bytes) -> bytes:
        line = header.model_dump_json().encode() + b"\n"
        nonce = os.urandom(12)
        sealed = AESGCM(self._box.derive_key(PURPOSE)).encrypt(nonce, archive, MAGIC + line)
        return MAGIC + line + nonce + sealed

    @staticmethod
    def header(blob: bytes) -> BackupHeader:
        return BackupCipher._split(blob)[0]

    def open(self, blob: bytes) -> bytes:
        """The archive, opened with the key in use or a previous one."""
        header, line, nonce, sealed = self._split(blob)
        for key in self._box.derive_keys(PURPOSE):
            try:
                return AESGCM(key).decrypt(nonce, sealed, MAGIC + line)
            except InvalidTag:
                continue
        raise BackupUnreadable(
            f"made with the key {header.key_fingerprint}, or damaged; the key in use is "
            f"{self._box.fingerprint()}. To restore it, set its key as "
            "AIOS_SECRETS_KEY_PREVIOUS and restart, then try again."
        )

    @staticmethod
    def _split(blob: bytes) -> tuple[BackupHeader, bytes, bytes, bytes]:
        if not blob.startswith(MAGIC):
            raise BackupUnreadable("not a backup of ai-os")
        rest = blob[len(MAGIC) :]
        end = rest.find(b"\n")
        if end < 0 or len(rest) < end + 1 + 12 + 16:
            raise BackupUnreadable("the backup is cut short")
        line = rest[: end + 1]
        try:
            header = BackupHeader.model_validate_json(line)
        except ValidationError as exc:
            raise BackupUnreadable("the backup's header is damaged") from exc
        nonce = rest[end + 1 : end + 13]
        return header, line, nonce, rest[end + 13 :]
