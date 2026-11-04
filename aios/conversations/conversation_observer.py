from abc import ABC, abstractmethod

from aios.conversations.conversation_event import ConversationEvent


class ConversationObserver(ABC):
    """Told about every conversation event as it happens, whichever channel the
    conversation is on. Must not raise and must not block."""

    @abstractmethod
    def notify(self, event: ConversationEvent) -> None: ...
