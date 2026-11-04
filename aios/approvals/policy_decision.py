from pydantic import BaseModel

from aios.approvals.policy_verdict import PolicyVerdict
from aios.entities.users.permission import Permission


class PolicyDecision(BaseModel):
    verdict: PolicyVerdict
    reason: str = ""
    question: str = ""
    approver_permission: Permission = Permission.APPROVE

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(verdict=PolicyVerdict.ALLOW)

    @classmethod
    def deny(cls, reason: str) -> "PolicyDecision":
        return cls(verdict=PolicyVerdict.DENY, reason=reason)

    @classmethod
    def ask(
        cls, question: str, approver_permission: Permission = Permission.APPROVE
    ) -> "PolicyDecision":
        return cls(
            verdict=PolicyVerdict.ASK,
            question=question,
            approver_permission=approver_permission,
        )
