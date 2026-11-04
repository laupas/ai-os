from abc import ABC, abstractmethod

from aios.entities.conversations.channel_binding import ChannelBinding


class ThreadStarter(ABC):
    """A channel that can open a new conversation by itself, e.g. for a scheduled run."""

    @abstractmethod
    async def start_thread(self, address: str, text: str) -> ChannelBinding:
        """Posts `text` at `address` and returns the new conversation's binding."""
