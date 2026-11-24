from aios.entities.users.audience_entry import EVERYONE
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.users.audience import Audience
from aios.users.authorizer import Authorizer


class PermissionAudience(Audience):
    """Administrators are in every audience. Anyone else is when the list names
    `everyone` or one of their groups. No list, or an empty one, means
    administrators only: that is what a new agent or connector starts as."""

    def __init__(self, authorizer: Authorizer) -> None:
        self._authorizer = authorizer

    def includes(self, user: User | None, available_to: list[str] | None) -> bool:
        if user is None:
            return False
        if self._authorizer.has(user, Permission.ADMINISTER):
            return True
        entries = set(available_to or [])
        return EVERYONE in entries or any(f"group:{g}" in entries for g in user.group_ids)
