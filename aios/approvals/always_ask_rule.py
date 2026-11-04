import json

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall


class AlwaysAskRule(ApprovalRule):
    """Asks before any tool listed under `approval.always` in config.yaml."""

    def __init__(self, tool_names: list[str]) -> None:
        self._tool_names = set(tool_names)

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name not in self._tool_names:
            return None
        details = json.dumps(call.tool_input, ensure_ascii=False)[:500]
        return PolicyDecision.ask(f"Allow {call.tool_name}?\n{details}")
