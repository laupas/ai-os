from dependency_injector import containers, providers

from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator


class CommonContainer(containers.DeclarativeContainer):
    clock = providers.Singleton(Clock)
    ids = providers.Singleton(IdGenerator)
