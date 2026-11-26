from datetime import datetime

from pydantic import BaseModel


class StoreInstallRecord(BaseModel):
    """Which source and version an installed item came from."""

    source: str
    version: str | None = None
    installed_at: datetime
    installed_by: str
    copy_of: str | None = None
    """A connector installed under another name: the id the source offers it as."""
