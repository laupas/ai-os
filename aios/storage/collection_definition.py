from pydantic import BaseModel, ConfigDict

from aios.entities.users.permission import Permission
from aios.storage.agent_access import AgentAccess


class CollectionDefinition(BaseModel):
    """What a collection stores and how agents may use it."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str
    entity: type[BaseModel]
    agent_access: AgentAccess = AgentAccess.NONE
    agent_writes_need_approval: bool = True
    approver_permission: Permission = Permission.APPROVE
    """Permission a user needs to approve an agent's write to this collection."""
    owner_field: str | None = None
    """The field naming whose a document is: a user id (None means shared with every
    user) or a list of user ids. Agents then reach only their turn user's documents
    and shared ones, and every write to a shared one asks for approval."""

    def visible_to(self, document: BaseModel, user_id: str) -> bool:
        if self.owner_field is None:
            return True
        owner = getattr(document, self.owner_field)
        if isinstance(owner, list):
            return user_id in owner
        return owner is None or owner == user_id

    def is_shared(self, document: BaseModel) -> bool:
        return self.owner_field is not None and getattr(document, self.owner_field) is None
