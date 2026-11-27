from aios.conversations.artifact_store import ArtifactStore
from aios.conversations.message_recorder import MessageRecorder
from aios.conversations.turn_canceller import TurnCanceller
from aios.entities.conversations.conversation import Conversation
from aios.storage.collection import Collection


class ConversationDeleter:
    """Deletes a conversation, its message history and its artifacts, stopping
    its turn first.

    The agent's own session transcript (under CLAUDE_CONFIG_DIR) is left alone: it
    is the SDK's file, and nothing reaches it once the conversation is gone. A later
    message in the same Slack thread starts a new conversation.
    """

    def __init__(
        self,
        conversations: Collection[Conversation],
        recorder: MessageRecorder,
        canceller: TurnCanceller,
        artifacts: ArtifactStore | None = None,
    ) -> None:
        self._conversations = conversations
        self._recorder = recorder
        self._canceller = canceller
        self._artifacts = artifacts

    async def delete(self, conversation_id: str) -> None:
        self._canceller.cancel(conversation_id)
        if self._artifacts is not None:
            for message in await self._recorder.history(conversation_id):
                if message.artifact is not None:
                    await self._artifacts.delete(message.artifact.id)
        await self._recorder.forget(conversation_id)
        await self._conversations.delete(conversation_id)
