from abc import ABC, abstractmethod

from aios.entities.approvals.approval import Approval


class ApprovalPresenter(ABC):
    """Shows an approval question on a channel (e.g. as buttons).

    Answers come back through `ApprovalAnswerHandler.answer`.
    """

    @abstractmethod
    async def present(self, approval: Approval) -> None: ...
