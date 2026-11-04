from pydantic import BaseModel

from aios.entities.users.permission import Permission


class Role(BaseModel):
    """A named set of permissions. Stored, so roles can change without code."""

    id: str
    name: str
    permissions: set[Permission] = set()
