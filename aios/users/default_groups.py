from aios.entities.users.group import Group
from aios.entities.users.permission import Permission


class DefaultGroups:
    """The groups created on first start. Edit them under Settings -> Groups."""

    OWNER = "owner"
    MEMBER = "member"
    """Where new users go unless told otherwise."""

    def all(self) -> list[Group]:
        return [
            Group(id=self.OWNER, name="Administrators", permissions=set(Permission)),
            Group(id=self.MEMBER, name="Members", permissions={Permission.CHAT}),
            Group(
                id="trusted_contact",
                name="Trusted contacts",
                permissions={Permission.RECEIVE_UNAPPROVED},
            ),
        ]
