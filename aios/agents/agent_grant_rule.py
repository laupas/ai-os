from aios.agents.agent_catalog import AgentCatalog
from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.users.audience import Audience

DELEGATE_TOOLS = ("Task", "Agent")


class AgentGrantRule(ApprovalRule):
    """Refuses a tool, skill, connector or delegation the calling agent was not granted.

    It never allows anything itself: a granted call goes on to the rules after it,
    so approvals still apply.

    Also refuses an agent, delegation or connector not available to the user the
    turn is for: the options of a turn leave them out, and this holds even if one
    slipped through.
    """

    def __init__(
        self, agents: AgentCatalog, connectors: ConnectorCatalog, audience: Audience
    ) -> None:
        self._agents = agents
        self._connectors = connectors
        self._audience = audience

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        spec = self._agents.get(call.agent) if call.agent else None
        if spec is None or not spec.enabled:
            return PolicyDecision.deny(
                f"{call.agent or 'An unknown agent'} is not an enabled agent."
            )
        if spec.id != AgentCatalog.ORCHESTRATOR and not self._audience.includes(
            call.user, spec.available_to
        ):
            return PolicyDecision.deny(f"{spec.name} is not available to {call.user.name}.")
        tool = call.tool_name
        if tool.startswith("mcp__"):
            server, _, name = tool[5:].partition("__")
            if not self._connectors.is_enabled(server):
                return PolicyDecision.deny(f"The connector {server} is switched off.")
            if server not in spec.connectors:
                return PolicyDecision.deny(f"{spec.name} may not use the connector {server}.")
            if server != ConnectorCatalog.BUILTIN and not self._connectors.available_to(
                server, call.user, self._audience
            ):
                return PolicyDecision.deny(
                    f"The connector {server} is not available to {call.user.name}."
                )
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
            target_spec = next((d for d in self._agents.delegates() if d.id == target), None)
            if target_spec is None:
                return PolicyDecision.deny(f"{target or 'That agent'} is not an enabled agent.")
            if not self._audience.includes(call.user, target_spec.available_to):
                return PolicyDecision.deny(f"{target} is not available to {call.user.name}.")
            return None
        if tool not in spec.builtin_tools:
            return PolicyDecision.deny(f"{spec.name} may not use {tool}.")
        return None
