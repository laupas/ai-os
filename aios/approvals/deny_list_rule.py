from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall


class DenyListRule(ApprovalRule):
    """Refuses tools listed under `approval.deny` in config.yaml."""

    def __init__(self, tool_names: list[str]) -> None:
        self._tool_names = set(tool_names)

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name in self._tool_names:
            return PolicyDecision.deny(f"The tool {call.tool_name} is switched off for ai-os.")
        return None
