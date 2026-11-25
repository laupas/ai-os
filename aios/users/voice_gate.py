from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer


class VoiceGate:
    """Whether a voice note from a channel account is transcribed: only for a user
    with the `voice` permission, since every transcription costs. Decided before
    the audio is fetched, so nothing is spent on anyone else."""

    def __init__(self, users: Collection[User], authorizer: Authorizer) -> None:
        self._users = users
        self._authorizer = authorizer

    def allows(self, sender: ChannelAccount) -> bool:
        return self._authorizer.has(self._user(sender), Permission.VOICE)

    def may_be_told(self, sender: ChannelAccount) -> bool:
        """Whether to say why a voice note was not listened to: only to someone who
        may chat. Anybody else hears nothing, as for any message they send."""
        return self._authorizer.has(self._user(sender), Permission.CHAT)

    def _user(self, sender: ChannelAccount) -> User | None:
        return self._users.find(lambda u: u.has_account(sender.channel, sender.address))
