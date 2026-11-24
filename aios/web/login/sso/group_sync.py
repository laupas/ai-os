import logging

from aios.entities.users.group import Group
from aios.entities.users.user import User
from aios.storage.collection import Collection

log = logging.getLogger(__name__)


class GroupSync:
    """Keeps a user's mapped groups as a sign-in provider says: a group the map
    names is added when the provider sent its value and taken away when it did not.
    Groups the map does not name (given by hand in the console) are never touched.

    A group with a powerful right (`Permission.powerful`) is never filled from a token,
    or whoever controls the provider's groups would control ai-os."""

    def __init__(self, users: Collection[User], groups: Collection[Group]) -> None:
        self._users = users
        self._groups = groups

    def refusal(self, group_id: str) -> str | None:
        """Why `group_id` may not be filled from a provider's groups, or None."""
        group = self._groups.get(group_id)
        if group is None:
            return f"there is no group {group_id}"
        if any(p.powerful for p in group.permissions):
            return f"group {group_id} administers ai-os; it is never filled from a sign-in"
        return None

    async def sync(self, user: User, values: list[str], group_map: dict[str, str]) -> User:
        mapped = {g for g in group_map.values() if self.refusal(g) is None}
        wanted = {group_map[v] for v in values if group_map.get(v) in mapped}
        kept = [g for g in user.group_ids if g not in mapped or g in wanted]
        group_ids = kept + sorted(wanted - set(kept))
        if group_ids == user.group_ids:
            return user
        updated = user.model_copy(update={"group_ids": group_ids})
        await self._users.put(updated)
        log.info("sso: %s's groups are now %s", user.name, ", ".join(group_ids) or "none")
        return updated
