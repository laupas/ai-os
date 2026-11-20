import json
from collections.abc import Callable

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.config.approval_config import ApprovalConfig


class AlwaysAskRule(ApprovalRule):
    """Asks before any tool listed under `approval.always` in aios.yaml, as it is now."""

    def __init__(self, config: Callable[[], ApprovalConfig]) -> None:
        self._config = config

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name not in self._config().always:
            return None
        details = json.dumps(call.tool_input, ensure_ascii=False)[:500]
        return PolicyDecision.ask(f"Allow {call.tool_name}?\n{details}")
