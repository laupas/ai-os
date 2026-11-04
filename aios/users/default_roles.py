from aios.entities.users.permission import Permission
from aios.entities.users.role import Role


class DefaultRoles:
    """The roles created on first start. Edit the files in /data/roles afterwards."""

    OWNER = "owner"

    def all(self) -> list[Role]:
        return [
            Role(id=self.OWNER, name="Owner", permissions=set(Permission)),
            Role(id="member", name="Member", permissions={Permission.CHAT}),
            Role(
                id="trusted_contact",
                name="Trusted contact",
                permissions={Permission.RECEIVE_UNAPPROVED},
            ),
        ]
