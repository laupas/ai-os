import logging

from aios.channels.authored_sender import AuthoredSender
from aios.channels.channel_directory import ChannelDirectory
from aios.channels.message_channel import MessageChannel
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.user import User
from aios.progress.progress_event import ProgressEvent

log = logging.getLogger(__name__)


class ConversationDelivery:
    """Sends to a conversation wherever it lives: every channel binding it has.

    A conversation is the unit, not a channel. Replies and progress go to all of
    its bindings, and a user's message is mirrored to the bindings it did not come
    from, so each place reads as the whole conversation. A binding on a channel that
    is no longer enabled is skipped, and one failing place never stops the others.
    """

    def __init__(self, channels: ChannelDirectory) -> None:
        self._channels = channels

    async def send(self, conversation: Conversation, text: str) -> None:
        for binding, channel in self._places(conversation):
            try:
                await channel.send(binding, text)
            except Exception:
                log.exception("could not send to %s in %s", binding.channel, conversation.id)

    async def mirror(
        self, conversation: Conversation, origin: ChannelBinding, author: User, text: str
    ) -> None:
        for binding, channel in self._places(conversation):
            if binding.same_place(origin):
                continue
            try:
                if isinstance(channel, AuthoredSender):
                    await channel.send_as(binding, text, author, origin.channel)
                else:
                    await channel.send(binding, f"*{author.name} ({origin.channel}):* {text}")
            except Exception:
                log.exception("could not mirror to %s in %s", binding.channel, conversation.id)

    async def report(self, conversation: Conversation, event: ProgressEvent) -> None:
        for binding, _ in self._places(conversation):
            try:
                await self._channels.reporter_for(binding.channel).report(binding, event)
            except Exception:
                log.exception("could not report progress to %s", binding.channel)

    async def finish(self, conversation: Conversation) -> None:
        for binding, _ in self._places(conversation):
            try:
                await self._channels.reporter_for(binding.channel).finish(binding)
            except Exception:
                log.exception("could not finish progress on %s", binding.channel)

    def _places(self, conversation: Conversation) -> list[tuple[ChannelBinding, MessageChannel]]:
        places = []
        for binding in conversation.bindings:
            try:
                places.append((binding, self._channels.get(binding.channel)))
            except KeyError:
                continue  # a channel that is not enabled any more
        return places
