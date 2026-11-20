import html
import re
from collections.abc import Callable
from typing import Any

from aios.channels.teams.teams_threads import CHANNEL, TeamsThreads
from aios.conversations.attachment import Attachment
from aios.conversations.inbound_message import InboundMessage
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.channel_account import ChannelAccount

FILE = "application/vnd.microsoft.teams.file.download.info"
_TAG = re.compile(r"<[^>]+>")


class TeamsActivityReader:
    """Decides whether a Teams message activity is for ai-os and turns it into an
    `InboundMessage`.

    For ai-os: every message in a personal chat, a message that mentions the bot,
    and any message in a thread or chat that is already a conversation. Card button
    presses (activities with a `value`) are not messages and are left to the channel.
    The sender is their Microsoft Entra object id.
    """

    def __init__(self, threads: TeamsThreads, is_known: Callable[[ChannelBinding], bool]) -> None:
        self._threads = threads
        self._is_known = is_known

    def read(self, activity: dict[str, Any]) -> InboundMessage | None:
        if activity.get("type") != "message" or activity.get("value") is not None:
            return None
        sender = self.sender_of(activity)
        conversation = activity.get("conversation") or {}
        if sender is None or not conversation.get("id"):
            return None
        binding = self._threads.binding_of(conversation)
        text, mentioned = self._without_mention(activity)
        personal = conversation.get("conversationType") == "personal"
        if not (personal or mentioned or self._is_known(binding)):
            return None
        attachments = self._attachments(activity)
        if not text and not attachments:
            return None
        return InboundMessage(binding=binding, sender=sender, text=text, attachments=attachments)

    @staticmethod
    def sender_of(activity: dict[str, Any]) -> ChannelAccount | None:
        object_id = (activity.get("from") or {}).get("aadObjectId")
        if not object_id:
            return None
        return ChannelAccount(channel=CHANNEL, address=str(object_id).lower())

    @staticmethod
    def _without_mention(activity: dict[str, Any]) -> tuple[str, bool]:
        text = str(activity.get("text") or "")
        bot_id = (activity.get("recipient") or {}).get("id")
        mentioned = False
        for entity in activity.get("entities") or []:
            if (
                entity.get("type") == "mention"
                and (entity.get("mentioned") or {}).get("id") == bot_id
            ):
                mentioned = True
                text = text.replace(str(entity.get("text") or ""), "")
        return html.unescape(_TAG.sub("", text)).strip(), mentioned

    @staticmethod
    def _attachments(activity: dict[str, Any]) -> list[Attachment]:
        """Files sent in a personal chat, each with a download link that needs no token."""
        return [
            Attachment(
                name=str(a.get("name") or "file"),
                mime_type="",
                url=(a.get("content") or {}).get("downloadUrl"),
            )
            for a in activity.get("attachments") or []
            if a.get("contentType") == FILE
        ]
