from abc import ABC, abstractmethod

from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount


class InboundHandler(ABC):
    """What a channel hands its incoming messages to."""

    @abstractmethod
    async def handle(self, message: InboundMessage) -> None: ...

    @abstractmethod
    async def cancel(self, binding: ChannelBinding, sender: ChannelAccount) -> bool:
        """Stops the running turn of the conversation at `binding`, if any."""

    @abstractmethod
    def is_known(self, binding: ChannelBinding) -> bool:
        """Whether `binding` already belongs to a conversation. Lets a channel follow
        a thread it was mentioned in without needing a mention in every reply."""
