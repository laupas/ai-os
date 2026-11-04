from aios.conversations.message_recorder import MessageRecorder
from aios.conversations.turn_canceller import TurnCanceller
from aios.entities.conversations.conversation import Conversation
from aios.storage.collection import Collection


class ConversationDeleter:
    """Deletes a conversation and its message history, stopping its turn first.

    The agent's own session transcript (under CLAUDE_CONFIG_DIR) is left alone: it
    is the SDK's file, and nothing reaches it once the conversation is gone. A later
    message in the same Slack thread starts a new conversation.
    """

    def __init__(
        self,
        conversations: Collection[Conversation],
        recorder: MessageRecorder,
        canceller: TurnCanceller,
    ) -> None:
        self._conversations = conversations
        self._recorder = recorder
        self._canceller = canceller

    async def delete(self, conversation_id: str) -> None:
        self._canceller.cancel(conversation_id)
        await self._recorder.forget(conversation_id)
        await self._conversations.delete(conversation_id)
