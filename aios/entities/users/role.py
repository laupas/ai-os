from pydantic import BaseModel

from aios.entities.users.permission import Permission


class Role(BaseModel):
    """Older form of a group: a named set of permissions. Read only to turn each
    into a group of the same id (`GroupsMigration`)."""

    id: str
    name: str
    permissions: set[Permission] = set()
