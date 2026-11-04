from abc import ABC, abstractmethod

from aios.entities.users.channel_account import ChannelAccount


class ApprovalAnswerHandler(ABC):
    """Receives answers to approvals, e.g. from a button a channel rendered."""

    @abstractmethod
    async def answer(self, approval_id: str, answer: str, sender: ChannelAccount) -> bool:
        """Returns False when the approval is not pending or the sender may not answer."""
