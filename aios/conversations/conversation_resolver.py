from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.user import User
from aios.storage.collection import Collection


class ConversationResolver:
    """Finds the conversation a channel binding belongs to, creating it if new."""

    def __init__(
        self, conversations: Collection[Conversation], clock: Clock, ids: IdGenerator
    ) -> None:
        self._conversations = conversations
        self._clock = clock
        self._ids = ids

    def get(self, conversation_id: str) -> Conversation | None:
        return self._conversations.get(conversation_id)

    async def attach(self, conversation: Conversation, binding: ChannelBinding) -> Conversation:
        """Adds another place the conversation lives, e.g. the web console."""
        if conversation.is_bound_to(binding):
            return conversation
        return await self._conversations.put(
            conversation.model_copy(update={"bindings": [*conversation.bindings, binding]})
        )

    def find(self, binding: ChannelBinding) -> Conversation | None:
        return self._conversations.find(lambda c: c.is_bound_to(binding))

    async def resolve(
        self, binding: ChannelBinding, user: User, agent: str | None = None
    ) -> Conversation:
        """`agent` is used only when the conversation is new."""
        conversation = self.find(binding)
        if conversation is None:
            now = self._clock.now()
            conversation = await self._conversations.put(
                Conversation(
                    id=self._ids.new_id(),
                    participants=[user.id],
                    bindings=[binding],
                    agent=agent,
                    created_at=now,
                    updated_at=now,
                )
            )
        elif user.id not in conversation.participants:
            conversation = await self._conversations.put(
                conversation.model_copy(
                    update={"participants": [*conversation.participants, user.id]}
                )
            )
        return conversation

    async def save(self, conversation: Conversation) -> Conversation:
        return await self._conversations.put(
            conversation.model_copy(update={"updated_at": self._clock.now()})
        )
