from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.channels.web.web_channel import WebChannel


class WebChannelType(ChannelType):
    """The chat in the web console. It needs no values: who is asking comes from the
    console's login proxy (`web.auth` in aios.yaml)."""

    def __init__(self, channel: WebChannel) -> None:
        self._channel = channel

    @property
    def name(self) -> str:
        return "web"

    @property
    def title(self) -> str:
        return "Web console"

    @property
    def description(self) -> str:
        return (
            "Chat in this console, with progress, a stop button and approvals. Off, the "
            "console still works for settings, but has no chat."
        )

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.CHAT}

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        # The very instance the web server talks to.
        return self._channel
