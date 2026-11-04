from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection


class Authorizer:
    """Answers whether a user's roles grant a permission."""

    def __init__(self, roles: Collection[Role]) -> None:
        self._roles = roles

    def permissions_of(self, user: User) -> set[Permission]:
        granted: set[Permission] = set()
        for role_id in user.role_ids:
            role = self._roles.get(role_id)
            if role is not None:
                granted |= role.permissions
        return granted

    def has(self, user: User | None, permission: Permission) -> bool:
        return user is not None and permission in self.permissions_of(user)
