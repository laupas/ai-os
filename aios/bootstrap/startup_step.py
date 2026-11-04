from abc import ABC, abstractmethod


class StartupStep(ABC):
    """Prepares stored data once it is loaded and before anything runs: default
    roles and the owner, connectors, agents and skills from their seeds."""

    @abstractmethod
    async def run(self) -> None: ...
