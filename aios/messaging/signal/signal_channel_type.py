import asyncio

import aiohttp

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.setup_problem import SetupProblem
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
                text=(
                    "Run signal-cli-rest-api next to ai-os, as a container both can reach "
                    "(for example on the same Docker network)."
                ),
                link="https://github.com/bbernhard/signal-cli-rest-api",
                details=[
                    "Signal is for sending only: agents send messages to people's numbers; "
                    "nobody chats with ai-os on Signal.",
                ],
            ),
            SetupStep(
                text=(
                    "Give it a number: link it to an existing Signal account as a device, or "
                    "register a number of its own."
                ),
                details=[
                    "To link: open /v1/qrcodelink?device_name=ai-os on signal-cli-rest-api "
                    "in a browser, and scan the code in the Signal app under Settings → "
                    "Linked devices.",
                    "To register a new number, follow signal-cli-rest-api's guide; it needs "
                    "a number that can receive a code by SMS or call.",
                ],
            ),
            SetupStep(
                text=(
                    "Enter its address and the number below, with country code, and Test. "
                    "Then switch the channel on, save, and restart ai-os."
                ),
                details=[
                    "The address is as ai-os reaches the container, for example "
                    "http://signal-api:8080.",
                ],
            ),
            SetupStep(
                text=(
                    "For each person: their phone number with country code (+41…) as a signal"
                    " account under Settings → Users."
                ),
                details=[
                    "Agents can then message them, subject to approvals.",
                ],
            ),
        ]

    @property
    def problems(self) -> list[SetupProblem]:
        return [
            SetupProblem(
                symptom='Test: "… is not registered in signal-api".',
                fix=(
                    "Enter the number exactly as linked or registered there, with + and "
                    "country code."
                ),
            ),
            SetupProblem(
                symptom='Test: "signal-api unreachable".',
                fix=(
                    "Check the address, and that the container runs and is on a network ai-os"
                    " can reach."
                ),
            ),
            SetupProblem(
                symptom='Test: "no answer within 30 s".',
                fix=(
                    "In its normal mode signal-cli-rest-api is slow; try again, or run it in "
                    "json-rpc mode."
                ),
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
