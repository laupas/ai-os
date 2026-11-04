from aios.approvals.approval_presenter import ApprovalPresenter
from aios.channels.message_channel import MessageChannel
from aios.entities.approvals.approval import Approval


class TextApprovalPresenter(ApprovalPresenter):
    """Fallback for channels without buttons: asks in text, the reply is matched."""

    def __init__(self, channel: MessageChannel) -> None:
        self._channel = channel

    async def present(self, approval: Approval) -> None:
        options = " / ".join(approval.options)
        await self._channel.send(approval.binding, f"{approval.question}\nReply with: {options}")
