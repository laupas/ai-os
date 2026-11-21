import logging

from aios.channels.channel_directory import ChannelDirectory
from aios.entities.users.user import User
from aios.messaging.sender_directory import SenderDirectory

log = logging.getLogger(__name__)

SKIPPED = {"web"}


class CodeMessenger:
    """Sends a user a short message on the first enabled channel that reaches them:
    a chat channel that can open a conversation (Slack, Teams), else a sender
    (Signal, mail). Never the web console itself."""

    def __init__(self, channels: ChannelDirectory, senders: SenderDirectory) -> None:
        self._channels = channels
        self._senders = senders

    def reachable(self, user: User) -> list[str]:
        """The channels, in the order tried, on which `user` has an account."""
        names = [
            n
            for n in self._channels.names()
            if n not in SKIPPED and self._channels.thread_starter_for(n) is not None
        ]
        names += [n for n in self._senders.names() if n not in SKIPPED and n not in names]
        return [n for n in names if user.account_for(n) is not None]

    async def send(self, user: User, text: str) -> str | None:
        """The channel it went out on, or None when none worked."""
        for name in self.reachable(user):
            account = user.account_for(name)
            if account is None:
                continue
            chat = name in self._channels.names()
            starter = self._channels.thread_starter_for(name) if chat else None
            try:
                if starter is not None:
                    await starter.start_thread(account.address, text)
                    return name
                sender = self._senders.get(name)
                if sender is not None and (await sender.send(account, text)).ok:
                    return name
            except Exception:
                log.exception("sign-in code to %s on %s failed", user.name, name)
        return None
