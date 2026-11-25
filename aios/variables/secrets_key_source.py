from pathlib import Path

from aios.variables.secrets_key_missing import SecretsKeyMissing
from aios.variables.secrets_key_origin import SecretsKeyOrigin

MISSING = (
    "AIOS_SECRETS_KEY is not set. ai-os encrypts its stored secrets with it and keeps "
    "it out of the data dir. Generate one (openssl rand -base64 48), keep it in a "
    "password manager, set it in the environment (.env, the cloud's app settings) and "
    "start again."
)


class SecretsKeySource:
    """The keys ai-os encrypts and decrypts its secrets with.

    The key comes from `AIOS_SECRETS_KEY`, outside the data dir, so a copy of the data
    (a backup, a snapshot) opens no secret. Replacing it: the new key in
    `AIOS_SECRETS_KEY`, the one before in `AIOS_SECRETS_KEY_PREVIOUS`; at start
    `SecretsKeyRotation` moves everything onto the new key.

    An older ai-os generated the key into `<data>/secrets.key` when the setting was
    missing. Such a file is still read: as the key in use while the setting is missing,
    as one more previous key once it is set, until `SecretsKeyRotation` removes it.
    """

    def __init__(self, setting: str | None, previous: str | None, legacy_file: Path) -> None:
        self._setting = setting or None
        self._previous = previous or None
        self._file = Path(legacy_file)

    def current(self) -> str:
        if self._setting:
            return self._setting
        legacy = self._legacy()
        if legacy:
            return legacy
        raise SecretsKeyMissing(MISSING)

    def previous(self) -> list[str]:
        """Keys that still open secrets but encrypt none: newest first."""
        keys = [k for k in (self._previous, self._legacy() if self._setting else None) if k]
        current = self.current()
        return [k for i, k in enumerate(keys) if k != current and k not in keys[:i]]

    def origin(self) -> SecretsKeyOrigin:
        return SecretsKeyOrigin.SETTING if self._setting else SecretsKeyOrigin.DATA_DIR

    def legacy_file(self) -> Path | None:
        """The key file of an older ai-os, while there is one."""
        return self._file if self._file.exists() else None

    def legacy_key(self) -> str | None:
        return self._legacy()

    def remove_legacy_file(self) -> None:
        self._file.unlink(missing_ok=True)

    def _legacy(self) -> str | None:
        if not self._file.exists():
            return None
        return self._file.read_text(encoding="utf-8").strip() or None
