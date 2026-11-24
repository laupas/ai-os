from pydantic import BaseModel


class Group(BaseModel):
    """People who share roles: every member has the group's roles on top of their
    own. Stored in the configuration repository, like roles; who is in it is on
    each user (`group_ids`)."""

    id: str
    name: str
    description: str = ""
    role_ids: list[str] = []
