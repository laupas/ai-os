from datetime import datetime

from pydantic import BaseModel


class BackupContents(BaseModel):
    """What an uploaded backup holds, checked, for the administrator to confirm."""

    created_at: datetime
    aios_version: str
    key_fingerprint: str
    files: int
    size: int
    """Unpacked, in bytes."""
    folders: dict[str, int]
    """Files per top-level entry of the data dir."""
