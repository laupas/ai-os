from collections.abc import Callable

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.config.approval_config import ApprovalConfig


class DenyListRule(ApprovalRule):
    """Refuses tools listed under `approval.deny` in aios.yaml, as it is now."""

    def __init__(self, config: Callable[[], ApprovalConfig]) -> None:
        self._config = config

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name in self._config().deny:
            return PolicyDecision.deny(f"The tool {call.tool_name} is switched off for ai-os.")
        return None
