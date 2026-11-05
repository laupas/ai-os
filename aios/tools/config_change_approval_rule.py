import json

from aios.agents.agent_catalog import AgentCatalog
from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.entities.users.permission import Permission
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.config_delete_tool import ConfigDeleteTool
from aios.tools.config_put_tool import ConfigPutTool

_CONFIG_PREFIX = AiosToolServer.TOOL_PREFIX + "config_"
_WRITES = {
    AiosToolServer.TOOL_PREFIX + ConfigPutTool.NAME: "save",
    AiosToolServer.TOOL_PREFIX + ConfigDeleteTool.NAME: "delete",
}


class ConfigChangeApprovalRule(ApprovalRule):
    """The `config_*` tools belong to the configurator agent alone, whatever an
    agent was granted: an agent that could change agents could grant itself anything.
    Every change is asked of an administrator, with the whole document shown."""

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if not call.tool_name.startswith(_CONFIG_PREFIX):
            return None
        if call.agent != AgentCatalog.CONFIGURATOR:
            return PolicyDecision.deny(
                f"Only {AgentCatalog.CONFIGURATOR} may read or change the configuration."
            )
        action = _WRITES.get(call.tool_name)
        if action is None:
            return PolicyDecision.allow()
        kind = str(call.tool_input.get("kind", ""))
        target = call.tool_input.get("document") or {"id": call.tool_input.get("name")}
        details = json.dumps(target, ensure_ascii=False, indent=1)[:3000]
        return PolicyDecision.ask(
            f"Allow ai-os to {action} this in {kind}?\n{details}", Permission.ADMINISTER
        )
