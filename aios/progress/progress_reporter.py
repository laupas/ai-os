from abc import ABC, abstractmethod

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.progress.progress_event import ProgressEvent


class ProgressReporter(ABC):
    """Shows what the agent is doing while a turn runs. Optional for a channel."""

    @abstractmethod
    async def report(self, binding: ChannelBinding, event: ProgressEvent) -> None: ...

    @abstractmethod
    async def finish(self, binding: ChannelBinding) -> None: ...
