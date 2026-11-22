from collections.abc import Callable
from typing import Any

from aios.entities.conversations.channel_binding import ChannelBinding

CHANNEL = "teams"
CHAT = "chat"
_MESSAGE_ID = ";messageid="
REMEMBERED = 5000


class TeamsThreads:
    """Maps Teams conversations to bindings and back.

    A post in a Teams channel has threads: its conversation id ends in
    `;messageid=<root>`, which becomes the binding's thread.

    In a personal or group chat it depends on `in_chats`. With it, chats work like
    channels: a message at the top of the chat starts a conversation, answered in
    its thread (Teams' "Reply in thread"), and a reply in that thread continues it;
    the thread is `chat-<root>`. Without it, the whole chat is one conversation
    (thread `chat`) until a new one is started there (`/new`, or a scheduled run),
    which is remembered only while ai-os runs: after a restart the chat is back at
    thread `chat`. "Reply with quote" on a message goes back to that message's
    conversation, and the chat stays there; a scheduled post is found from its
    thread even after a restart, other messages only while ai-os runs. The bot's
    first answer in such a conversation quotes where it began (`quote_next`); its
    cards do not, as Teams shows a quote above a card as a bubble of its own.
    """

    def __init__(self, in_chats: bool = False) -> None:
        self._in_chats = in_chats
        self._current: dict[str, str] = {}
        self._chats: dict[str, str] = {}
        self._messages: dict[str, str] = {}
        self._quotes: dict[tuple[str, str], str] = {}

    def binding_of(
        self,
        activity: dict[str, Any],
        is_known: Callable[[ChannelBinding], bool] = lambda binding: False,
    ) -> ChannelBinding:
        """`is_known` says whether a binding is a conversation already, to find the
        one a quoted message started."""
        conversation = activity.get("conversation") or {}
        conversation_id = str(conversation["id"])
        address, found, message_id = conversation_id.partition(_MESSAGE_ID)
        if found and conversation.get("conversationType") in (None, "channel"):
            return ChannelBinding(channel=CHANNEL, address=address, thread=message_id)
        chat_id = str(((activity.get("channelData") or {}).get("chat") or {}).get("id") or "")
        if chat_id:
            self._chats[address] = chat_id
        root = self._root_of(activity)
        if self._in_chats and root:
            return ChannelBinding(channel=CHANNEL, address=address, thread=f"{CHAT}-{root}")
        quoted = self._quoted_thread(activity, address, is_known)
        if quoted:
            self._current[address] = quoted
        binding = ChannelBinding(
            channel=CHANNEL, address=address, thread=self._current.get(address, CHAT)
        )
        if activity.get("value") is None:
            self.remember(str(activity.get("id") or ""), binding)
            if quoted:
                self.quote_next(binding, str(activity.get("id") or ""))
        return binding

    def remember(self, message_id: str, binding: ChannelBinding) -> None:
        """Notes that the chat message `message_id` belongs to `binding`, for quotes."""
        if not message_id or not self.is_chat(binding):
            return
        self._messages[message_id] = binding.thread
        while len(self._messages) > REMEMBERED:
            del self._messages[next(iter(self._messages))]

    def restart(self, address: str, key: str) -> ChannelBinding:
        """Starts a new conversation in the chat at `address`; `key` makes it unique.
        With threads in chats, `key` must be the id of the message at its top."""
        thread = f"{CHAT}-{key}"
        self._current[address] = thread
        return ChannelBinding(channel=CHANNEL, address=address, thread=thread)

    def reply_chain(self, binding: ChannelBinding) -> tuple[str, str] | None:
        """Where to reply in a chat `binding`'s thread, if it has one: the chat's id
        (`channelData.chat.id`, which Teams wants for that, not the conversation id;
        known once someone wrote there since ai-os started) and the root message."""
        root = binding.thread.removeprefix(f"{CHAT}-")
        if self._in_chats and self.is_chat(binding) and root.isdigit():
            return self._chats.get(binding.address, binding.address), root
        return None

    def quote_next(self, binding: ChannelBinding, message_id: str) -> None:
        """The bot's next message in a chat `binding` quotes `message_id`."""
        if message_id.isdigit() and self.is_chat(binding):
            self._quotes[(binding.address, binding.thread)] = message_id

    def take_quote(self, binding: ChannelBinding) -> str | None:
        """The message to quote in the bot's next message for `binding`, once; none
        in a thread, which shows where it belongs by itself."""
        quote = self._quotes.pop((binding.address, binding.thread), None)
        return None if self.reply_chain(binding) else quote

    @staticmethod
    def is_chat(binding: ChannelBinding) -> bool:
        return binding.thread == CHAT or binding.thread.startswith(f"{CHAT}-")

    @classmethod
    def conversation_id(cls, binding: ChannelBinding) -> str:
        """The Teams conversation to post into for `binding`."""
        if cls.is_chat(binding):
            return binding.address
        return f"{binding.address}{_MESSAGE_ID}{binding.thread}"

    def _quoted_thread(
        self,
        activity: dict[str, Any],
        address: str,
        is_known: Callable[[ChannelBinding], bool],
    ) -> str:
        for entity in activity.get("entities") or []:
            if entity.get("type") != "quotedReply":
                continue
            message_id = str((entity.get("quotedReply") or {}).get("messageId") or "")
            if message_id in self._messages:
                return self._messages[message_id]
            started = ChannelBinding(
                channel=CHANNEL, address=address, thread=f"{CHAT}-{message_id}"
            )
            if message_id and is_known(started):
                return started.thread
        return ""

    @staticmethod
    def _root_of(activity: dict[str, Any]) -> str:
        """The message at the top of the activity's thread: its own id at the top of
        the chat. A button press is in the thread of the card it was on."""
        channel_data = activity.get("channelData") or {}
        root = str((channel_data.get("replyChain") or {}).get("id") or "")
        if root.isdigit():
            return root
        own = str(activity.get("id") or "")
        return own if own.isdigit() and activity.get("value") is None else ""
