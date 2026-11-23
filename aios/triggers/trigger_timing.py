from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter

from aios.entities.triggers.trigger import Trigger


class TriggerTiming:
    """When a trigger fires next. Cron is evaluated in the trigger's own time
    zone, so "0 7 * * *" stays 07:00 local across daylight saving changes."""

    def next_after(self, trigger: Trigger, after: datetime) -> datetime | None:
        if trigger.once_at is not None:
            return trigger.once_at if trigger.last_fired_at is None else None
        zone = ZoneInfo(trigger.timezone)
        local = after.astimezone(zone)
        candidates = [croniter(expr, local).get_next(datetime) for expr in trigger.cron]
        return min(candidates) if candidates else None
