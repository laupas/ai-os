from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_type import ChannelType
from aios.channels.setup_problem import SetupProblem
from aios.channels.setup_step import SetupStep


class WebhookChannelType(ChannelType):
    """HTTP calls to destinations set up in the console, each with its own url,
    headers and body. Needs no values of its own: a destination's tokens are
    `${VAR}` in its templates."""

    @property
    def name(self) -> str:
        return "webhook"

    @property
    def title(self) -> str:
        return "Webhooks"

    @property
    def description(self) -> str:
        return (
            "Agents post to named destinations (an n8n flow, Home Assistant, a chat's incoming "
            "webhook), each with its own url, headers and body template."
        )

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.WEBHOOK}

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text=(
                    "Add a destination below: its url, the headers it needs, the fields an agent "
                    "fills in, and the body they go into."
                ),
                details=[
                    "{{text}} in the url, a header or the body is the agent's field `text`; "
                    "every field used must be declared under Fields.",
                    "${NAME} is the Variable NAME: put tokens there, never into the "
                    "destination itself, which is committed to the configuration repository.",
                    "A body written as JSON is sent as JSON; a value that is exactly "
                    '"{{field}}" keeps the field\'s type (a number stays a number).',
                ],
            ),
            SetupStep(
                text="Send a test from the destination, with sample fields.",
                details=["A test really calls the destination."],
            ),
            SetupStep(
                text=(
                    "Switch the channel on, save, and restart ai-os. Destinations themselves "
                    "apply at once, without a restart."
                ),
            ),
            SetupStep(
                text="Grant `send_webhook` (aios connector) to the agents that may post.",
                details=[
                    "Each destination asks for approval before every post unless set to allow; "
                    "deny keeps agents off it entirely.",
                ],
            ),
        ]

    @property
    def problems(self) -> list[SetupProblem]:
        return [
            SetupProblem(
                symptom='Test: "the Variable … is not set".',
                fix="Set that Variable under Variables, or correct the ${NAME} in the destination.",
            ),
            SetupProblem(
                symptom="Test: 401 or 403.",
                fix=(
                    "Check the token Variable and the header it goes into "
                    "(Authorization: Bearer ${NAME})."
                ),
            ),
        ]
