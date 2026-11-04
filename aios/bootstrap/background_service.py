from abc import ABC, abstractmethod


class BackgroundService(ABC):
    """Something that runs next to the channels for the life of the process."""

    @abstractmethod
    async def run(self) -> None: ...
