from aios.approvals.approval_policy import ApprovalPolicy
from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall


class RuleBasedApprovalPolicy(ApprovalPolicy):
    """Asks each rule in order; the first one with an opinion decides.

    When no rule objects, the call is allowed. Rules that deny unknown tools must
    therefore come first.
    """

    def __init__(self, rules: list[ApprovalRule]) -> None:
        self._rules = rules

    def evaluate(self, call: ToolCall) -> PolicyDecision:
        for rule in self._rules:
            decision = rule.evaluate(call)
            if decision is not None:
                return decision
        return PolicyDecision.allow()
