from collections.abc import Callable

from aios.messaging.message_sender import MessageSender


class SenderDirectory:
    """The enabled senders, created on first use."""

    def __init__(
        self, factories: dict[str, Callable[[], MessageSender]], enabled: list[str]
    ) -> None:
        unknown = set(enabled) - set(factories)
        if unknown:
            raise ValueError(f"unknown senders in config: {sorted(unknown)}")
        self._factories = factories
        self._enabled = list(enabled)
        self._senders: dict[str, MessageSender] = {}

    def names(self) -> list[str]:
        return list(self._enabled)

    def get(self, name: str) -> MessageSender | None:
        if name not in self._enabled:
            return None
        if name not in self._senders:
            self._senders[name] = self._factories[name]()
        return self._senders[name]
