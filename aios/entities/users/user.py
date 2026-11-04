from pydantic import BaseModel

from aios.entities.users.channel_account import ChannelAccount


class User(BaseModel):
    """Anyone ai-os talks to or sends to."""

    id: str
    name: str
    aliases: list[str] = []
    accounts: list[ChannelAccount] = []
    role_ids: list[str] = []
    notes: str | None = None

    def has_account(self, channel: str, address: str) -> bool:
        return any(a.channel == channel and a.address == address for a in self.accounts)

    def matches_name(self, name: str) -> bool:
        wanted = name.strip().casefold()
        return wanted in {n.casefold() for n in [self.name, *self.aliases]}

    def account_for(self, channel: str) -> ChannelAccount | None:
        return next((a for a in self.accounts if a.channel == channel), None)
