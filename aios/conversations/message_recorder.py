from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.conversations.conversation_event import ConversationEvent
from aios.conversations.conversation_observer import ConversationObserver
from aios.entities.conversations.message import Message
from aios.entities.conversations.message_role import MessageRole
from aios.storage.append_log import AppendLog


class MessageRecorder:
    """Appends to and reads a conversation's message history."""

    def __init__(
        self,
        log: AppendLog,
        clock: Clock,
        ids: IdGenerator,
        observers: list[ConversationObserver] | None = None,
    ) -> None:
        self._log = log
        self._clock = clock
        self._ids = ids
        self._observers = list(observers or [])

    async def record(
        self,
        conversation_id: str,
        role: MessageRole,
        text: str,
        channel: str,
        author_user_id: str | None = None,
    ) -> Message:
        message = Message(
            id=self._ids.new_id(),
            conversation_id=conversation_id,
            role=role,
            author_user_id=author_user_id,
            channel=channel,
            text=text,
            created_at=self._clock.now(),
        )
        await self._log.append(self._log_name(conversation_id), message.model_dump(mode="json"))
        event = ConversationEvent(conversation_id=conversation_id, kind="message", message=message)
        for observer in self._observers:
            observer.notify(event)
        return message

    async def history(self, conversation_id: str) -> list[Message]:
        records = await self._log.read_all(self._log_name(conversation_id))
        return [Message.model_validate(r) for r in records]

    async def forget(self, conversation_id: str) -> None:
        await self._log.delete(self._log_name(conversation_id))

    @staticmethod
    def _log_name(conversation_id: str) -> str:
        return f"conversations/{conversation_id}/messages"
