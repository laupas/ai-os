from datetime import datetime

from pydantic import BaseModel, Field


class TriggerRequest(BaseModel):
    """What the console may set on a trigger. The rest (id, when it last fired,
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
    webhook: bool = False
    """Whether a webhook may start it. Turned on, ai-os makes the token and shows
    it once; it is never set from here."""
