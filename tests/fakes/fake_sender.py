from aios.entities.users.channel_account import ChannelAccount
from aios.messaging.delivery_result import DeliveryResult
from aios.messaging.message_sender import MessageSender


class FakeSender(MessageSender):
    def __init__(self, name: str = "signal", ok: bool = True) -> None:
        self._name = name
        self._ok = ok
        self.sent: list[tuple[ChannelAccount, str, str | None]] = []

    @property
    def name(self) -> str:
        return self._name

    async def send(
        self, account: ChannelAccount, text: str, subject: str | None = None
    ) -> DeliveryResult:
        self.sent.append((account, text, subject))
        return DeliveryResult(ok=self._ok, detail="" if self._ok else "boom")
