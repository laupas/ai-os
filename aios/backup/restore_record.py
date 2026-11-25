from datetime import datetime

from pydantic import BaseModel

from aios.backup.backup_contents import BackupContents


class RestoreRecord(BaseModel):
    """A restore that ran at start: from which backup, and where the data it replaced
    was kept (`<data>/<kept_in>`), until an administrator removes it."""

    restored_at: datetime
    backup: BackupContents
    kept_in: str
    recorded: bool = False
    """Written to the audit trail (`RestoreAudit`), which only exists once ai-os runs."""
