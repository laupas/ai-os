from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleRequest(BaseModel):
    """What the console may set on a schedule. The rest (id, when it last fired,
    when it was made) is ai-os's to keep."""

    name: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    cron: list[str] = []
    once_at: datetime | None = None
    timezone: str = "Europe/Zurich"
    user_id: str
    agent: str | None = None
    enabled: bool = True
    max_lateness_minutes: int = Field(60, ge=1)
