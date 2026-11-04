import aiohttp

from aios.entities.users.channel_account import ChannelAccount
from aios.messaging.delivery_result import DeliveryResult
from aios.messaging.message_sender import MessageSender

RESEND_URL = "https://api.resend.com/emails"


class MailOverResendSender(MessageSender):
    """Sends mail through the Resend API, as helpino.ai and pergalino.ch do.

    Unlike those, a failed send is reported back, never swallowed.
    """

    def __init__(self, api_key: str | None, mail_from: str | None) -> None:
        self._api_key = api_key
        self._mail_from = mail_from

    @property
    def name(self) -> str:
        return "mail"

    async def send(
        self, account: ChannelAccount, text: str, subject: str | None = None
    ) -> DeliveryResult:
        if not self._api_key or not self._mail_from:
            return DeliveryResult(ok=False, detail="RESEND_API_KEY or AIOS_MAIL_FROM is not set")
        payload = {
            "from": self._mail_from,
            "to": [account.address],
            "subject": subject or "Message from ai-os",
            "text": text,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(RESEND_URL, json=payload) as response:
                    detail = await response.text()
                    return DeliveryResult(ok=response.status < 300, detail=detail[:500])
        except aiohttp.ClientError as exc:
            return DeliveryResult(ok=False, detail=f"Resend unreachable: {exc}")
