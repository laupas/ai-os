import json
from typing import Any

from pydantic import BaseModel

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.storage.collection import Collection
from aios.storage.collection_registry import CollectionRegistry
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.data_delete_tool import DataDeleteTool
from aios.tools.data_put_tool import DataPutTool

_DATA_PREFIX = AiosToolServer.TOOL_PREFIX + "data_"
_WRITES = {
    AiosToolServer.TOOL_PREFIX + DataPutTool.NAME: "save",
    AiosToolServer.TOOL_PREFIX + DataDeleteTool.NAME: "delete",
}


class DataAccessApprovalRule(ApprovalRule):
    """Refuses data tools outside a collection's agent access, and asks before a
    write when the collection's definition says writes need approval, or when the
    write creates, changes or deletes a document shared with every user."""

    def __init__(self, registry: CollectionRegistry) -> None:
        self._registry = registry

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if not call.tool_name.startswith(_DATA_PREFIX) or "collection" not in call.tool_input:
            return None
        name = str(call.tool_input["collection"])
        collection = self._registry.get(name)
        if collection is None or not collection.definition.agent_access.allows_read():
            return PolicyDecision.deny(f"No readable collection called {name!r}.")
        action = _WRITES.get(call.tool_name)
        if action is None:
            return PolicyDecision.allow()
        definition = collection.definition
        if not definition.agent_access.allows_write():
            return PolicyDecision.deny(f"The collection {name!r} is read-only for agents.")
        if not definition.agent_writes_need_approval and not self._touches_shared(
            collection, call.tool_input
        ):
            return PolicyDecision.allow()
        target = call.tool_input.get("document") or {"id": call.tool_input.get("id")}
        details = json.dumps(target, ensure_ascii=False, indent=1)[:1500]
        return PolicyDecision.ask(
            f"Allow ai-os to {action} this in {name}?\n{details}",
            definition.approver_permission,
        )

    @staticmethod
    def _touches_shared(collection: Collection[BaseModel], tool_input: dict[str, Any]) -> bool:
        definition = collection.definition
        if definition.owner_field is None:
            return False
        document = tool_input.get("document")
        if isinstance(document, dict) and (
            definition.owner_field in document and document[definition.owner_field] is None
        ):
            return True
        target_id = document.get("id") if isinstance(document, dict) else tool_input.get("id")
        existing = collection.get(str(target_id)) if target_id is not None else None
        return existing is not None and definition.is_shared(existing)
