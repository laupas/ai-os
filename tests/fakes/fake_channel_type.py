from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.messaging.message_sender import MessageSender
from aios.variables.variable_field import VariableField
from tests.fakes.fake_channel import FakeChannel
from tests.fakes.fake_sender import FakeSender


class FakeChannelType(ChannelType):
    """A channel that chats and sends, needs `FAKE_TOKEN`, and whose check passes
    only for the token `good`. Records what it was made from and checked with."""

    def __init__(self, name: str = "fake") -> None:
        self._name = name
        self.made_with: list[dict[str, str | None]] = []
        self.checked: list[dict[str, str | None]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def title(self) -> str:
        return "Fake"

    @property
    def description(self) -> str:
        return "For tests."

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.CHAT, ChannelCapability.SEND}

    @property
    def fields(self) -> list[VariableField]:
        return [
            VariableField(variable="FAKE_TOKEN", label="Token"),
            VariableField(variable="FAKE_URL", label="Address", secret=False, default="http://x"),
        ]

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        self.made_with.append(values)
        return FakeChannel(self._name)

    def create_sender(self, values: dict[str, str | None]) -> MessageSender:
        self.made_with.append(values)
        return FakeSender(self._name)

    async def check(self, values: dict[str, str | None]) -> ChannelCheckResult:
        self.checked.append(values)
        return ChannelCheckResult(ok=values["FAKE_TOKEN"] == "good", detail="checked")
