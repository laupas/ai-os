from abc import ABC, abstractmethod

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.conversations.inbound_handler import InboundHandler
from aios.entities.conversations.channel_binding import ChannelBinding


class MessageChannel(ABC):
    """A chat platform ai-os talks on. Progress and approval buttons are optional
    extras: implement `ProgressReporter` / `ApprovalPresenter` as well to offer them."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def start(self, inbound: InboundHandler, answers: ApprovalAnswerHandler) -> None:
        """Runs until the channel stops."""

    @abstractmethod
    async def send(self, binding: ChannelBinding, text: str) -> None: ...
