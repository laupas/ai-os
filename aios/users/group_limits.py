from aios.entities.users.group import Group
from aios.entities.users.user import User
from aios.storage.collection import Collection


class GroupLimits:
    """The limits a user's groups set for them, where any does."""

    def __init__(self, groups: Collection[Group]) -> None:
        self._groups = groups

    def messages_per_minute(self, user: User) -> int | None:
        """The most generous of their groups' limits; None when none sets one."""
        limits = [
            g.messages_per_minute
            for g in (self._groups.get(i) for i in user.group_ids)
            if g is not None and g.messages_per_minute is not None
        ]
        return max(limits) if limits else None
