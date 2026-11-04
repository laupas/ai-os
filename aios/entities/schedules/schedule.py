from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter
from pydantic import BaseModel, model_validator


class Schedule(BaseModel):
    """A prompt ai-os runs by itself, on cron times or once, for one user.

    Each run is a new conversation that runs as `user_id` and is opened wherever
    that user can be reached (their Slack DM, the web console, ...), like any other
    conversation. Where exactly is the user's accounts' business, not the schedule's.
    """

    id: str
    name: str
    prompt: str
    cron: list[str] = []
    """Five-field cron expressions in `timezone`; the earliest next one fires."""
    once_at: datetime | None = None
    """A single run instead of cron. Deleted after it fired."""
    timezone: str = "Europe/Zurich"
    user_id: str
    """Who the run is for: it runs with their permissions and reaches them."""
    agent: str | None = None
    """The agent each run goes to straight away; None asks the orchestrator."""
    enabled: bool = True
    max_lateness_minutes: int = 60
    """A run that is later than this (e.g. after downtime) is skipped, not replayed."""
    last_fired_at: datetime | None = None
    created_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _read_older_documents(cls, data: Any) -> Any:
        # Before 2026-11-01 a schedule named a channel and address to post to and a
        # `run_as_user_id`; the place is now the user's, so only the user is kept.
        if not isinstance(data, dict):
            return data
        if "user_id" not in data and "run_as_user_id" in data:
            data = {**data, "user_id": data["run_as_user_id"]}
        return {k: v for k, v in data.items() if k not in ("channel", "address", "run_as_user_id")}

    @model_validator(mode="after")
    def _check_timing(self) -> "Schedule":
        if bool(self.cron) == (self.once_at is not None):
            raise ValueError("set either `cron` or `once_at`, not both or neither")
        for expression in self.cron:
            if not croniter.is_valid(expression):
                raise ValueError(f"invalid cron expression: {expression!r}")
        ZoneInfo(self.timezone)  # raises for an unknown zone
        if self.once_at is not None and self.once_at.tzinfo is None:
            raise ValueError("`once_at` needs a timezone offset")
        return self
