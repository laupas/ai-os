import asyncio

from aios.conversations.conversation_event import ConversationEvent
from aios.conversations.conversation_observer import ConversationObserver


class WebEventHub(ConversationObserver):
    """Fans the events of every conversation, whatever its channel, out to the
    browser tabs watching it. A tab that is not watching misses them and reads the
    history when it comes back."""

    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[ConversationEvent]]] = {}

    def subscribe(self, conversation_id: str) -> asyncio.Queue[ConversationEvent]:
        queue: asyncio.Queue[ConversationEvent] = asyncio.Queue()
        self._queues.setdefault(conversation_id, set()).add(queue)
        return queue

    def unsubscribe(self, conversation_id: str, queue: asyncio.Queue[ConversationEvent]) -> None:
        queues = self._queues.get(conversation_id)
        if queues is not None:
            queues.discard(queue)
            if not queues:
                del self._queues[conversation_id]

    def notify(self, event: ConversationEvent) -> None:
        for queue in self._queues.get(event.conversation_id, set()):
            queue.put_nowait(event)
