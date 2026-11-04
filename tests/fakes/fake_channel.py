from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.channels.message_channel import MessageChannel
from aios.conversations.inbound_handler import InboundHandler
from aios.entities.conversations.channel_binding import ChannelBinding


class FakeChannel(MessageChannel):
    """Records what was sent; has no progress or buttons, so text fallbacks apply."""

    def __init__(self, name: str = "fake") -> None:
        self._name = name
        self.sent: list[tuple[ChannelBinding, str]] = []

    @property
    def name(self) -> str:
        return self._name

    async def start(self, inbound: InboundHandler, answers: ApprovalAnswerHandler) -> None:
        return None

    async def send(self, binding: ChannelBinding, text: str) -> None:
        self.sent.append((binding, text))

    def texts(self) -> list[str]:
        return [text for _, text in self.sent]
