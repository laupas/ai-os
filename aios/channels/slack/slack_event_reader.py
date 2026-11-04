import re
from collections.abc import Callable
from typing import Any

from aios.conversations.attachment import Attachment
from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount

_HANDLED_SUBTYPES = {None, "file_share", "thread_broadcast"}


class SlackEventReader:
    """Decides whether a Slack message event is for ai-os and turns it into an
    `InboundMessage`.

    For ai-os: every DM, a channel message that mentions the bot, and any reply in a
    thread that is already a conversation. Bots, edits and deletions are ignored.
    A top-level message starts its own thread, so each one is a new conversation.
    """

    def __init__(self, bot_user_id: str, is_known: Callable[[ChannelBinding], bool]) -> None:
        self._mention = re.compile(rf"<@{re.escape(bot_user_id)}>\s*")
        self._is_known = is_known

    def read(self, event: dict[str, Any]) -> InboundMessage | None:
        if event.get("bot_id") or event.get("subtype") not in _HANDLED_SUBTYPES:
            return None
        user, channel, ts = event.get("user"), event.get("channel"), event.get("ts")
        if not user or not channel or not ts:
            return None
        text = str(event.get("text") or "")
        binding = ChannelBinding(
            channel="slack", address=channel, thread=event.get("thread_ts") or ts
        )
        is_dm = event.get("channel_type") == "im"
        mentioned = bool(self._mention.search(text))
        if not (is_dm or mentioned or self._is_known(binding)):
            return None
        clean = self._mention.sub("", text).strip()
        attachments = self._attachments(event)
        if not clean and not attachments:
            return None
        return InboundMessage(
            binding=binding,
            sender=ChannelAccount(channel="slack", address=user),
            text=clean,
            attachments=attachments,
        )

    @staticmethod
    def _attachments(event: dict[str, Any]) -> list[Attachment]:
        return [
            Attachment(
                name=str(f.get("name") or f.get("id") or "file"),
                mime_type=str(f.get("mimetype") or ""),
                url=f.get("url_private_download") or f.get("url_private"),
            )
            for f in event.get("files") or []
        ]
