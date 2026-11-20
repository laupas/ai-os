from typing import Any

from aios.entities.conversations.channel_binding import ChannelBinding

CHANNEL = "teams"
CHAT = "chat"
_MESSAGE_ID = ";messageid="


class TeamsThreads:
    """Maps Teams conversations to bindings and back.

    A post in a Teams channel has threads: its conversation id ends in
    `;messageid=<root>`, which becomes the binding's thread. A personal or group
    chat has none, so the whole chat is one conversation (thread `chat`) until a
    new one is started there (`/new`, or a scheduled run), which is remembered
    only while ai-os runs: after a restart the chat is back at thread `chat`.
    """

    def __init__(self) -> None:
        self._current: dict[str, str] = {}

    def binding_of(self, conversation: dict[str, Any]) -> ChannelBinding:
        conversation_id = str(conversation["id"])
        root, found, message_id = conversation_id.partition(_MESSAGE_ID)
        if found:
            return ChannelBinding(channel=CHANNEL, address=root, thread=message_id)
        return ChannelBinding(
            channel=CHANNEL,
            address=conversation_id,
            thread=self._current.get(conversation_id, CHAT),
        )

    def restart(self, address: str, key: str) -> ChannelBinding:
        """Starts a new conversation in the chat at `address`; `key` makes it unique."""
        thread = f"{CHAT}-{key}"
        self._current[address] = thread
        return ChannelBinding(channel=CHANNEL, address=address, thread=thread)

    @staticmethod
    def is_chat(binding: ChannelBinding) -> bool:
        return binding.thread == CHAT or binding.thread.startswith(f"{CHAT}-")

    @classmethod
    def conversation_id(cls, binding: ChannelBinding) -> str:
        """The Teams conversation to post into for `binding`."""
        if cls.is_chat(binding):
            return binding.address
        return f"{binding.address}{_MESSAGE_ID}{binding.thread}"
