from dependency_injector import containers, providers

from aios.scheduler.schedule_runner import ScheduleRunner
from aios.scheduler.schedule_timing import ScheduleTiming
from aios.scheduler.scheduler_loop import SchedulerLoop


class SchedulerContainer(containers.DeclarativeContainer):
    schedules = providers.Dependency()
    users = providers.Dependency()
    channels = providers.Dependency()
    turns = providers.Dependency()
    clock = providers.Dependency()
    scheduler_config = providers.Dependency()

    timing = providers.Singleton(ScheduleTiming)
    runner = providers.Singleton(ScheduleRunner, users=users, channels=channels, turns=turns)
    loop = providers.Singleton(
        SchedulerLoop,
        schedules=schedules,
        timing=timing,
        runner=runner,
        clock=clock,
        tick_seconds=scheduler_config.provided.tick_seconds,
    )
