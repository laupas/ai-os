from datetime import datetime

from pydantic import BaseModel


class BackupHeader(BaseModel):
    """The readable start of a backup file: what it is and which key opens it. The
    rest is encrypted, and this header is bound to it, so it cannot be altered."""

    format: int = 1
    created_at: datetime
    aios_version: str
    key_fingerprint: str
    """The secrets key the backup was made with (`SecretBox.fingerprint`): a restore
    needs that key, as AIOS_SECRETS_KEY or AIOS_SECRETS_KEY_PREVIOUS."""
    left_out: list[str]
    """What the backup does not hold, relative to the data dir."""
