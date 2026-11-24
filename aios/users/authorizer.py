from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection


class Authorizer:
    """Answers whether a user's roles grant a permission: their own roles and
    those of their groups."""

    def __init__(self, roles: Collection[Role], groups: Collection[Group]) -> None:
        self._roles = roles
        self._groups = groups

    def role_ids_of(self, user: User) -> list[str]:
        """The user's own roles, then their groups' roles, each once."""
        found = list(user.role_ids)
        for group_id in user.group_ids:
            group = self._groups.get(group_id)
            if group is not None:
                found += [r for r in group.role_ids if r not in found]
        return found

    def permissions_of(self, user: User) -> set[Permission]:
        granted: set[Permission] = set()
        for role_id in self.role_ids_of(user):
            role = self._roles.get(role_id)
            if role is not None:
                granted |= role.permissions
        return granted

    def has(self, user: User | None, permission: Permission) -> bool:
        return user is not None and permission in self.permissions_of(user)
