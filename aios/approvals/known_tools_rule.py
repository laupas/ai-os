from collections.abc import Callable

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall


class KnownToolsRule(ApprovalRule):
    """Denies every tool that is not explicitly enabled.

    The connector prefixes are asked for on every call, since connectors can be
    switched on and off while ai-os runs.
    """

    def __init__(self, builtin_tools: list[str], tool_prefixes: Callable[[], list[str]]) -> None:
        self._builtin = set(builtin_tools)
        self._prefixes = tool_prefixes

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name in self._builtin or call.tool_name.startswith(tuple(self._prefixes())):
            return None
        return PolicyDecision.deny(f"The tool {call.tool_name} is not enabled for ai-os.")
