from datetime import datetime

from pydantic import BaseModel


class ConnectorStatus(BaseModel):
    """What the last turn reported about a connector."""

    name: str
    status: str | None = None
    """As Claude Code reports it: connected, failed, needs-auth, …"""
    tools: list[str] = []
    error: str | None = None
    seen_at: datetime
