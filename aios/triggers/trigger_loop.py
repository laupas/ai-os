import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

from aios.bootstrap.background_service import BackgroundService
from aios.common.clock import Clock
from aios.config.triggers_config import TriggersConfig
from aios.entities.triggers.trigger import Trigger
from aios.storage.collection import Collection
from aios.triggers.trigger_runner import TriggerRunner
from aios.triggers.trigger_timing import TriggerTiming

log = logging.getLogger(__name__)


class TriggerLoop(BackgroundService):
    """Checks the triggers every tick and starts the due ones, each in its own task.

    A trigger seen for the first time is only stamped, so it fires from its next
    slot on rather than for a slot in the past. A slot missed by more than
    `max_lateness_minutes` (e.g. the host was down) is skipped, not replayed.

    `triggers` in aios.yaml is read on every tick: switched off, nothing fires
    until it is switched on again, without a restart.
    """

    def __init__(
        self,
        triggers: Collection[Trigger],
        timing: TriggerTiming,
        runner: TriggerRunner,
        clock: Clock,
        config: Callable[[], TriggersConfig],
    ) -> None:
        self._triggers = triggers
        self._timing = timing
        self._runner = runner
        self._clock = clock
        self._config = config
        self._tasks: set[asyncio.Task[None]] = set()

    async def run(self) -> None:
        log.info("triggers running, %d triggers", len(self._triggers.all()))
        while True:
            config = self._config()
            if config.enabled:
                try:
                    await self.tick()
                except Exception:
                    log.exception("triggers tick failed")
            await asyncio.sleep(config.tick_seconds)

    async def tick(self) -> None:
        now = self._clock.now()
        for trigger in self._triggers.filter(lambda s: s.enabled):
            if trigger.cron and trigger.last_fired_at is None:
                await self._triggers.put(trigger.model_copy(update={"last_fired_at": now}))
                continue
            due = self._timing.next_after(trigger, trigger.last_fired_at or now)
            if due is None or due > now:
                continue
            if now - due > timedelta(minutes=trigger.max_lateness_minutes):
                log.warning("trigger %s: skipping the run due at %s", trigger.name, due)
                await self._mark_fired(trigger, now)
                continue
            await self._mark_fired(trigger, now)
            self._start(trigger)

    async def _mark_fired(self, trigger: Trigger, now) -> None:  # type: ignore[no-untyped-def]
        if trigger.once_at is not None:
            await self._triggers.delete(trigger.id)
        else:
            await self._triggers.put(trigger.model_copy(update={"last_fired_at": now}))

    def _start(self, trigger: Trigger) -> None:
        log.info("trigger %s firing", trigger.name)
        task = asyncio.create_task(self._runner.run(trigger))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
