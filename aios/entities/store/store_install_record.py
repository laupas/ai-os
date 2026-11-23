from datetime import datetime

from pydantic import BaseModel


class StoreInstallRecord(BaseModel):
    """Which source and version an installed item came from."""

    source: str
    version: str | None = None
    installed_at: datetime
    installed_by: str
