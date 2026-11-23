from dependency_injector import containers, providers

from aios.triggers.trigger_loop import TriggerLoop
from aios.triggers.trigger_runner import TriggerRunner
from aios.triggers.trigger_timing import TriggerTiming


class TriggersContainer(containers.DeclarativeContainer):
    triggers = providers.Dependency()
    users = providers.Dependency()
    channels = providers.Dependency()
    turns = providers.Dependency()
    clock = providers.Dependency()
    triggers_config = providers.Dependency()  # a getter: aios.yaml as it is now

    timing = providers.Singleton(TriggerTiming)
    runner = providers.Singleton(TriggerRunner, users=users, channels=channels, turns=turns)
    loop = providers.Singleton(
        TriggerLoop,
        triggers=triggers,
        timing=timing,
        runner=runner,
        clock=clock,
        config=triggers_config,
    )
