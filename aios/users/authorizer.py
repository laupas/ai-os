from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection


class Authorizer:
    """Answers whether a user's groups grant a permission, with the rights a
    permission brings along (`Permission.implied`)."""

    def __init__(self, groups: Collection[Group]) -> None:
        self._groups = groups

    def permissions_of(self, user: User) -> set[Permission]:
        granted: set[Permission] = set()
        for group_id in user.group_ids:
            group = self._groups.get(group_id)
            if group is not None:
                granted |= group.permissions
        for permission in list(granted):
            granted |= permission.implied
        return granted

    def has(self, user: User | None, permission: Permission) -> bool:
        return user is not None and permission in self.permissions_of(user)
