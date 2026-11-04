from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter

from aios.entities.schedules.schedule import Schedule


class ScheduleTiming:
    """When a schedule fires next. Cron is evaluated in the schedule's own time
    zone, so "0 7 * * *" stays 07:00 local across daylight saving changes."""

    def next_after(self, schedule: Schedule, after: datetime) -> datetime | None:
        if schedule.once_at is not None:
            return schedule.once_at if schedule.last_fired_at is None else None
        zone = ZoneInfo(schedule.timezone)
        local = after.astimezone(zone)
        candidates = [croniter(expr, local).get_next(datetime) for expr in schedule.cron]
        return min(candidates) if candidates else None
