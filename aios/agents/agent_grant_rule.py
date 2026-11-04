from aios.agents.agent_catalog import AgentCatalog
from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.connectors.connector_catalog import ConnectorCatalog

DELEGATE_TOOLS = ("Task", "Agent")


class AgentGrantRule(ApprovalRule):
    """Refuses a tool, skill, connector or delegation the calling agent was not granted.

    It never allows anything itself: a granted call goes on to the rules after it,
    so approvals still apply.
    """

    def __init__(self, agents: AgentCatalog, connectors: ConnectorCatalog) -> None:
        self._agents = agents
        self._connectors = connectors

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        spec = self._agents.get(call.agent) if call.agent else None
        if spec is None or not spec.enabled:
            return PolicyDecision.deny(
                f"{call.agent or 'An unknown agent'} is not an enabled agent."
            )
        tool = call.tool_name
        if tool.startswith("mcp__"):
            server, _, name = tool[5:].partition("__")
            if not self._connectors.is_enabled(server):
                return PolicyDecision.deny(f"The connector {server} is switched off.")
            if server not in spec.connectors:
                return PolicyDecision.deny(f"{spec.name} may not use the connector {server}.")
            granted = spec.connectors[server]
            if granted is not None and name not in granted:
                return PolicyDecision.deny(f"{spec.name} may not use {tool}.")
            return None
        if tool == "Skill":
            skill = str(call.tool_input.get("skill", ""))
            if skill not in spec.skills:
                return PolicyDecision.deny(f"{spec.name} may not use the skill {skill}.")
            return None
        if tool in DELEGATE_TOOLS:
            if not any(t in spec.builtin_tools for t in DELEGATE_TOOLS):
                return PolicyDecision.deny(f"{spec.name} may not delegate.")
            target = str(call.tool_input.get("subagent_type", ""))
            if target not in {d.id for d in self._agents.delegates()}:
                return PolicyDecision.deny(f"{target or 'That agent'} is not an enabled agent.")
            return None
        if tool not in spec.builtin_tools:
            return PolicyDecision.deny(f"{spec.name} may not use {tool}.")
        return None
