from abc import ABC, abstractmethod

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.user import User


class AuthoredSender(ABC):
    """A channel that can show a message as written by someone, e.g. a user's own
    words typed on another channel. Optional; without it the text is labelled."""

    @abstractmethod
    async def send_as(self, binding: ChannelBinding, text: str, author: User, via: str) -> None:
        """`via` names the channel the author actually wrote on."""
