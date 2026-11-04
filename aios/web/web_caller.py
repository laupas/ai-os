from pydantic import BaseModel

from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User


class WebCaller(BaseModel):
    """The user behind a request, with the web account they came in on."""

    user: User
    account: ChannelAccount
    permissions: set[Permission]

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions
