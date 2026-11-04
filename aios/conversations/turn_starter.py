from abc import ABC, abstractmethod

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.user import User


class TurnStarter(ABC):
    """Runs a turn that did not come in as a chat message, e.g. a scheduled prompt."""

    @abstractmethod
    async def start_turn(
        self, user: User, bindings: list[ChannelBinding], text: str, agent: str | None = None
    ) -> None:
        """Opens one conversation in all of `bindings` (the first is where the turn
        counts as asked from) and runs `text` there. `text` is not shown as if the
        user had written it. `agent` answers instead of the orchestrator."""
