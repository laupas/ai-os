from pydantic import BaseModel

from aios.entities.users.channel_account import ChannelAccount


class OwnerConfig(BaseModel):
    """The first user, created once when no user exists yet."""

    name: str
    accounts: list[ChannelAccount] = []
