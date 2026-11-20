import asyncio

import aiohttp

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.setup_step import SetupStep
from aios.messaging.message_sender import MessageSender
from aios.messaging.signal.signal_sender import SignalSender
from aios.variables.variable_field import VariableField

URL = "SIGNAL_API_URL"
NUMBER = "SIGNAL_SENDER"
CHECK_SECONDS = 30  # signal-api in its normal mode starts signal-cli for each request


class SignalChannelType(ChannelType):
    """Signal through signal-cli-rest-api, as a number paired with it."""

    @property
    def name(self) -> str:
        return "signal"

    @property
    def title(self) -> str:
        return "Signal"

    @property
    def description(self) -> str:
        return (
            "Agents send messages to users' Signal numbers. Needs signal-cli-rest-api "
            "running, with a number registered or linked there."
        )

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.SEND}

    @property
    def fields(self) -> list[VariableField]:
        return [
            VariableField(
                variable=URL,
                label="signal-cli-rest-api address",
                secret=False,
                default="http://signal-api:8080",
            ),
            VariableField(
                variable=NUMBER,
                label="Sending number",
                hint="The number registered in signal-cli-rest-api, with country code.",
                placeholder="+41…",
            ),
        ]

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text="Run signal-cli-rest-api next to ai-os (a Docker container).",
                link="https://github.com/bbernhard/signal-cli-rest-api",
            ),
            SetupStep(
                text="Register a number there, or link it to an existing Signal account as a "
                "device (scan the QR code from /v1/qrcodelink?device_name=ai-os).",
            ),
            SetupStep(
                text="For each person: their phone number with country code as a signal account "
                "under Users.",
            ),
        ]

    def create_sender(self, values: dict[str, str | None]) -> MessageSender:
        return SignalSender(api_url=values[URL] or "", sender_number=values[NUMBER])

    async def check(self, values: dict[str, str | None]) -> ChannelCheckResult:
        url, number = (values[URL] or "").rstrip("/"), values[NUMBER]
        if not url or not number:
            return ChannelCheckResult(ok=False, detail="the address and the number are needed")
        try:
            async with asyncio.timeout(CHECK_SECONDS), aiohttp.ClientSession() as session:
                async with session.get(f"{url}/v1/accounts") as response:
                    if response.status >= 300:
                        return ChannelCheckResult(
                            ok=False, detail=f"signal-api answered {response.status}"
                        )
                    accounts = await response.json()
        except TimeoutError:
            return ChannelCheckResult(ok=False, detail=f"no answer within {CHECK_SECONDS} s")
        except aiohttp.ClientError as exc:
            return ChannelCheckResult(ok=False, detail=f"signal-api unreachable: {exc}")
        if number not in accounts:
            return ChannelCheckResult(ok=False, detail=f"{number} is not registered in signal-api")
        return ChannelCheckResult(ok=True, detail=f"{number} is registered and reachable")
