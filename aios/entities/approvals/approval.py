from datetime import datetime

from pydantic import BaseModel

from aios.entities.approvals.approval_status import ApprovalStatus
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.permission import Permission


class Approval(BaseModel):
    """A question put to a human, with a fixed set of answers.

    A tool approval is the same thing with the options Yes and No.
    """

    id: str
    conversation_id: str
    binding: ChannelBinding
    question: str
    options: list[str]
    approver_permission: Permission = Permission.APPROVE
    status: ApprovalStatus = ApprovalStatus.PENDING
    answer: str | None = None
    answered_by: str | None = None
    created_at: datetime
    answered_at: datetime | None = None

    def option_matching(self, text: str) -> str | None:
        wanted = text.strip().casefold()
        return next((o for o in self.options if o.casefold() == wanted), None)
