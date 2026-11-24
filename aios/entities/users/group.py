from pydantic import BaseModel, Field

from aios.entities.users.permission import Permission


class Group(BaseModel):
    """People who share rights: every member has the group's permissions, and the
    agents and connectors available to the group. Users get rights only through
    groups. Stored in the configuration repository; who is in a group is kept on
    each user (`group_ids`). `everyone` is built in and not stored: everybody is in
    it, and it grants no permission."""

    id: str
    name: str
    description: str = ""
    permissions: set[Permission] = set()
    role_ids: list[str] = Field(default=[], exclude=True)
    """Read, never written. Older form: roles whose permissions the group gave.
    Moved into `permissions` at the next start (`GroupsMigration`)."""
