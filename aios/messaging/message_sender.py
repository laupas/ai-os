from abc import ABC, abstractmethod

from aios.entities.users.channel_account import ChannelAccount
from aios.messaging.delivery_result import DeliveryResult


class MessageSender(ABC):
    """Delivers a message outside the chat, e.g. by Signal or mail.

    `name` matches the `channel` of the `ChannelAccount` it can deliver to.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def send(
        self, account: ChannelAccount, text: str, subject: str | None = None
    ) -> DeliveryResult: ...
