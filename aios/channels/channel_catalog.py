from collections.abc import Callable

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_type import ChannelType
from aios.channels.channel_values import ChannelValues
from aios.channels.message_channel import MessageChannel
from aios.config.channel_config import ChannelConfig
from aios.messaging.message_sender import MessageSender


class ChannelCatalog:
    """The channel types ai-os knows, and which are on in aios.yaml. Builds what
    `ChannelDirectory` and `SenderDirectory` hand out, so nothing that uses a
    channel needs to know where it came from."""

    def __init__(
        self,
        types: list[ChannelType],
        config: dict[str, ChannelConfig],
        values: ChannelValues,
    ) -> None:
        self._types = {t.name: t for t in types}
        unknown = sorted(set(config) - set(self._types))
        if unknown:
            raise ValueError(f"unknown channels in config: {unknown}")
        self._config = config
        self._values = values

    def all(self) -> list[ChannelType]:
        return list(self._types.values())

    def get(self, name: str) -> ChannelType | None:
        return self._types.get(name)

    def is_on(self, name: str) -> bool:
        config = self._config.get(name)
        return config is not None and config.enabled

    def enabled(self, capability: ChannelCapability) -> list[str]:
        return [n for n, t in self._types.items() if self.is_on(n) and capability in t.capabilities]

    def channel_factories(self) -> dict[str, Callable[[], MessageChannel]]:
        return {
            t.name: self._factory(t, t.create_channel, strict=True)
            for t in self._types.values()
            if ChannelCapability.CHAT in t.capabilities
        }

    def sender_factories(self) -> dict[str, Callable[[], MessageSender]]:
        return {
            t.name: self._factory(t, t.create_sender, strict=False)
            for t in self._types.values()
            if ChannelCapability.SEND in t.capabilities
        }

    def _factory[T](
        self, channel: ChannelType, create: Callable[[dict[str, str | None]], T], strict: bool
    ) -> Callable[[], T]:
        """A chat channel without its values does not start; a sender is made anyway
        and says what is missing when asked to send, as an agent can be told that."""

        def make() -> T:
            missing = self._values.missing(channel)
            if strict and missing:
                raise RuntimeError(f"{channel.title} needs {', '.join(missing)}")
            return create(self._values.of(channel))

        return make
