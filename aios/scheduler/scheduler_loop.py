import asyncio
import logging
from datetime import timedelta

from aios.bootstrap.background_service import BackgroundService
from aios.common.clock import Clock
from aios.entities.schedules.schedule import Schedule
from aios.scheduler.schedule_runner import ScheduleRunner
from aios.scheduler.schedule_timing import ScheduleTiming
from aios.storage.collection import Collection

log = logging.getLogger(__name__)


class SchedulerLoop(BackgroundService):
    """Checks the schedules every tick and starts the due ones, each in its own task.

    A schedule seen for the first time is only stamped, so it fires from its next
    slot on rather than for a slot in the past. A slot missed by more than
    `max_lateness_minutes` (e.g. the host was down) is skipped, not replayed.
    """

    def __init__(
        self,
        schedules: Collection[Schedule],
        timing: ScheduleTiming,
        runner: ScheduleRunner,
        clock: Clock,
        tick_seconds: float,
    ) -> None:
        self._schedules = schedules
        self._timing = timing
        self._runner = runner
        self._clock = clock
        self._tick = tick_seconds
        self._tasks: set[asyncio.Task[None]] = set()

    async def run(self) -> None:
        log.info("scheduler running, %d schedules", len(self._schedules.all()))
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("scheduler tick failed")
            await asyncio.sleep(self._tick)

    async def tick(self) -> None:
        now = self._clock.now()
        for schedule in self._schedules.filter(lambda s: s.enabled):
            if schedule.cron and schedule.last_fired_at is None:
                await self._schedules.put(schedule.model_copy(update={"last_fired_at": now}))
                continue
            due = self._timing.next_after(schedule, schedule.last_fired_at or now)
            if due is None or due > now:
                continue
            if now - due > timedelta(minutes=schedule.max_lateness_minutes):
                log.warning("schedule %s: skipping the run due at %s", schedule.name, due)
                await self._mark_fired(schedule, now)
                continue
            await self._mark_fired(schedule, now)
            self._start(schedule)

    async def _mark_fired(self, schedule: Schedule, now) -> None:  # type: ignore[no-untyped-def]
        if schedule.once_at is not None:
            await self._schedules.delete(schedule.id)
        else:
            await self._schedules.put(schedule.model_copy(update={"last_fired_at": now}))

    def _start(self, schedule: Schedule) -> None:
        log.info("schedule %s firing", schedule.name)
        task = asyncio.create_task(self._runner.run(schedule))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
