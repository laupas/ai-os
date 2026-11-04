from abc import ABC, abstractmethod

from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall


class ApprovalPolicy(ABC):
    @abstractmethod
    def evaluate(self, call: ToolCall) -> PolicyDecision: ...
