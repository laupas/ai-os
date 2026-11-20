import aiohttp

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.setup_problem import SetupProblem
from aios.channels.setup_step import SetupStep
from aios.messaging.mail.mail_over_resend_sender import MailOverResendSender
from aios.messaging.message_sender import MessageSender
from aios.variables.variable_field import VariableField

KEY = "RESEND_API_KEY"
FROM = "AIOS_MAIL_FROM"
DOMAINS_URL = "https://api.resend.com/domains"


class MailChannelType(ChannelType):
    """Mail through the Resend API."""

    @property
    def name(self) -> str:
        return "mail"

    @property
    def title(self) -> str:
        return "Mail"

    @property
    def description(self) -> str:
        return "Agents send mail to users' addresses through Resend, from a domain verified there."

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.SEND}

    @property
    def fields(self) -> list[VariableField]:
        return [
            VariableField(
                variable=KEY,
                label="Resend API key",
                hint="resend.com → API Keys.",
                placeholder="re_…",
            ),
            VariableField(
                variable=FROM,
                label="From",
                hint="An address at a domain verified in Resend.",
                secret=False,
                placeholder="ai-os <ai-os@example.com>",
            ),
        ]

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text=(
                    "Create a Resend account and add the domain to send from; add the DNS "
                    "records Resend shows at your DNS provider, and wait until the domain is "
                    "Verified."
                ),
                link="https://resend.com/domains",
                details=[
                    "Mail is for sending only: agents send mail to people's addresses.",
                ],
            ),
            SetupStep(
                text="Create an API key; sending access is enough.",
                link="https://resend.com/api-keys",
                details=[
                    "It is shown once: paste it into the key below.",
                ],
            ),
            SetupStep(
                text=(
                    "Enter the key and a From address at the verified domain, and Test. Then "
                    "switch the channel on, save, and restart ai-os."
                ),
                details=[
                    "The From address may carry a name: ai-os <ai-os@example.com>.",
                ],
            ),
            SetupStep(
                text=(
                    "For each person: their mail address as a mail account under Settings → Users."
                ),
                details=[
                    "Agents can then mail them, subject to approvals.",
                ],
            ),
        ]

    @property
    def problems(self) -> list[SetupProblem]:
        return [
            SetupProblem(
                symptom='Test: "key accepted, but … is not a verified domain".',
                fix=(
                    "Verify the From address's domain in Resend (the DNS records), or use an "
                    "address at a domain that is verified."
                ),
            ),
            SetupProblem(
                symptom='Test: "Resend refused the key".',
                fix="Create a new API key in Resend and enter it again.",
            ),
        ]

    def create_sender(self, values: dict[str, str | None]) -> MessageSender:
        return MailOverResendSender(api_key=values[KEY], mail_from=values[FROM])

    async def check(self, values: dict[str, str | None]) -> ChannelCheckResult:
        if not values[KEY] or not values[FROM]:
            return ChannelCheckResult(ok=False, detail="the key and the from address are needed")
        headers = {"Authorization": f"Bearer {values[KEY]}"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(DOMAINS_URL) as response:
                    body = await response.json(content_type=None)
                    status = response.status
        except (aiohttp.ClientError, ValueError) as exc:
            return ChannelCheckResult(ok=False, detail=f"Resend unreachable: {exc}")
        # A key for sending only may not list domains, which still proves it valid.
        if status == 401 and isinstance(body, dict) and body.get("name") == "restricted_api_key":
            return ChannelCheckResult(ok=True, detail="key accepted (sending only)")
        if status >= 300:
            message = body.get("message") if isinstance(body, dict) else None
            return ChannelCheckResult(
                ok=False, detail=f"Resend refused the key: {message or status}"
            )
        sender_domain = (values[FROM] or "").rsplit("@", 1)[-1].strip("> ").lower()
        verified = {
            d.get("name", "").lower()
            for d in (body.get("data") or [])
            if d.get("status") == "verified"
        }
        if sender_domain not in verified:
            return ChannelCheckResult(
                ok=False, detail=f"key accepted, but {sender_domain} is not a verified domain"
            )
        return ChannelCheckResult(ok=True, detail=f"key accepted, {sender_domain} verified")
