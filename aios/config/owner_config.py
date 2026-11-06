from pydantic import BaseModel, ConfigDict

from aios.entities.users.channel_account import ChannelAccount


class OwnerConfig(BaseModel):
    """The first user, created once when no user exists yet."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    name: str
    accounts: list[ChannelAccount] = []
