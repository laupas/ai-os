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
