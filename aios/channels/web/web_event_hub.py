import asyncio

from aios.conversations.conversation_event import ConversationEvent
from aios.conversations.conversation_observer import ConversationObserver

REPLAYED = frozenset({"progress", "delta"})


class WebEventHub(ConversationObserver):
    """Fans the events of every conversation, whatever its channel, out to the
    browser tabs watching it.

    Recorded messages a tab reads from the history when it comes back. What a
    running turn did so far (its steps and the reply being written) is recorded only
    when the turn ends, so the hub keeps it and replays it to a tab that subscribes
    in the middle of a turn. Pending approvals come with the history instead.
    """

    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[ConversationEvent]]] = {}
        self._turns: dict[str, list[ConversationEvent]] = {}

    def subscribe(self, conversation_id: str) -> asyncio.Queue[ConversationEvent]:
        queue: asyncio.Queue[ConversationEvent] = asyncio.Queue()
        for event in self._turns.get(conversation_id, []):
            queue.put_nowait(event)
        self._queues.setdefault(conversation_id, set()).add(queue)
        return queue

    def unsubscribe(self, conversation_id: str, queue: asyncio.Queue[ConversationEvent]) -> None:
        queues = self._queues.get(conversation_id)
        if queues is not None:
            queues.discard(queue)
            if not queues:
                del self._queues[conversation_id]

    def notify(self, event: ConversationEvent) -> None:
        if event.kind in REPLAYED:
            self._turns.setdefault(event.conversation_id, []).append(event)
        elif event.kind == "done":
            self._turns.pop(event.conversation_id, None)
        for queue in self._queues.get(event.conversation_id, set()):
            queue.put_nowait(event)
