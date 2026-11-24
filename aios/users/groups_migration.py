import logging

import yaml

from aios.bootstrap.startup_step import StartupStep
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config_repo.git_document_store import GitDocumentStore
from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.web.aios_yaml_file import AiosYamlFile

log = logging.getLogger(__name__)


class GroupsMigration(StartupStep):
    """Groups replace roles: each role becomes a group of the same id with its
    permissions (or adds them to a group of that id), a group that gave roles gets
    their permissions instead, every user is put in the groups their roles became,
    and the roles are removed. Agent access set for `roles` in aios.yaml
    (`collection_access`) moves to `groups`. Does nothing once no role is left."""

    def __init__(
        self,
        store: GitDocumentStore,
        users: Collection[User],
        roles: Collection[Role],
        groups: Collection[Group],
        config: AiosYamlFile | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._users = users
        self._roles = roles
        self._groups = groups

    async def run(self) -> None:
        roles = {r.id: r for r in self._roles.all()}
        stale_groups = [g for g in self._groups.all() if g.role_ids]
        stale_users = [u for u in self._users.all() if u.role_ids]
        if not (roles or stale_groups or stale_users):
            return
        async with self._store.batch("Groups replace roles"):
            for role in roles.values():
                group = self._groups.get(role.id)
                if group is None:
                    group = Group(id=role.id, name=role.name, permissions=set(role.permissions))
                else:
                    group = group.model_copy(
                        update={"permissions": group.permissions | role.permissions}
                    )
                await self._groups.put(group)
            for group in [g for g in self._groups.all() if g.role_ids]:
                given: set[Permission] = set()
                for role_id in group.role_ids:
                    role = roles.get(role_id)
                    given |= role.permissions if role is not None else set()
                await self._groups.put(
                    group.model_copy(
                        update={"permissions": group.permissions | given, "role_ids": []}
                    )
                )
            for user in [u for u in self._users.all() if u.role_ids]:
                group_ids = list(dict.fromkeys([*user.group_ids, *user.role_ids]))
                await self._users.put(
                    user.model_copy(update={"group_ids": group_ids, "role_ids": []})
                )
            for role_id in roles:
                await self._roles.delete(role_id)
        await self._move_collection_access()
        log.info(
            "groups replace roles: %d roles became groups, %d users moved into them",
            len(roles),
            len(stale_users),
        )

    async def _move_collection_access(self) -> None:
        if self._config is None:
            return
        text = self._config.read()
        try:
            section = (yaml.safe_load(text) or {}).get("collection_access") or {}
        except yaml.YAMLError:
            return
        if "roles" not in section:
            return
        moved = {("groups" if k == "roles" else k): v for k, v in section.items()}
        if "groups" in section:
            moved["groups"] = section["groups"]
        text = ConfigYamlEditor().replace_section(text, "collection_access", moved)
        await self._config.write(text, "aios.yaml: collection access for roles is for groups now")
