from abc import ABC, abstractmethod

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.message_channel import MessageChannel
from aios.channels.setup_problem import SetupProblem
from aios.channels.setup_step import SetupStep
from aios.messaging.message_sender import MessageSender
from aios.variables.variable_field import VariableField


class ChannelType(ABC):
    """One kind of channel ai-os can use: what it is, what it can do, which values
    it needs, and how to make it from them. A new channel is one of these plus one
    entry in `ChannelsContainer.types`.

    `values` holds every field's value by variable name, None when unset; `create_*`
    are only called when the channel is on, after a restart.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """As in aios.yaml and in users' channel accounts."""

    @property
    @abstractmethod
    def title(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> set[ChannelCapability]: ...

    @property
    def fields(self) -> list[VariableField]:
        return []

    @property
    def setup(self) -> list[SetupStep]:
        """How to set the channel up on the provider's side, for the console."""
        return []

    @property
    def problems(self) -> list[SetupProblem]:
        """What commonly goes wrong while setting it up, and the fix, for the console."""
        return []

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        raise NotImplementedError(f"{self.name} cannot be chatted with")

    def create_sender(self, values: dict[str, str | None]) -> MessageSender:
        raise NotImplementedError(f"{self.name} cannot send messages")

    async def check(self, values: dict[str, str | None]) -> ChannelCheckResult | None:
        """Tries the values without sending anything; None when there is no such test."""
        return None
