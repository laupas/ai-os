from abc import ABC, abstractmethod

from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall


class ApprovalRule(ABC):
    """One concern of the approval policy. Returns None when it has no opinion."""

    @abstractmethod
    def evaluate(self, call: ToolCall) -> PolicyDecision | None: ...
