from abc import ABC, abstractmethod

from aios.approvals.approval_presenter import ApprovalPresenter


class ApprovalPresenterResolver(ABC):
    @abstractmethod
    def presenter_for(self, channel: str) -> ApprovalPresenter: ...
