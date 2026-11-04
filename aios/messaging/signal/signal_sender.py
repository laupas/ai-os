import aiohttp

from aios.entities.users.channel_account import ChannelAccount
from aios.messaging.delivery_result import DeliveryResult
from aios.messaging.message_sender import MessageSender


class SignalSender(MessageSender):
    """Sends through signal-cli-rest-api (`POST /v2/send`) as the paired number."""

    def __init__(self, api_url: str, sender_number: str | None) -> None:
        self._api_url = api_url.rstrip("/")
        self._sender_number = sender_number

    @property
    def name(self) -> str:
        return "signal"

    async def send(
        self, account: ChannelAccount, text: str, subject: str | None = None
    ) -> DeliveryResult:
        if not self._sender_number:
            return DeliveryResult(ok=False, detail="SIGNAL_SENDER is not configured")
        body = f"{subject}\n\n{text}" if subject else text
        payload = {"message": body, "number": self._sender_number, "recipients": [account.address]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self._api_url}/v2/send", json=payload) as response:
                    detail = await response.text()
                    return DeliveryResult(ok=response.status < 300, detail=detail[:500])
        except aiohttp.ClientError as exc:
            return DeliveryResult(ok=False, detail=f"signal-api unreachable: {exc}")
