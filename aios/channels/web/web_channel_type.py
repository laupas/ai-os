from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.channels.setup_problem import SetupProblem
from aios.channels.setup_step import SetupStep
from aios.channels.web.web_channel import WebChannel


class WebChannelType(ChannelType):
    """The chat in the web console. It needs no values: who is asking comes from the
    console's login proxy (`web.auth` in aios.yaml)."""

    def __init__(self, channel: WebChannel) -> None:
        self._channel = channel

    @property
    def name(self) -> str:
        return "web"

    @property
    def title(self) -> str:
        return "Web console"

    @property
    def description(self) -> str:
        return (
            "Chat in this console, with progress, a stop button and approvals. Off, the "
            "console still works for settings, but has no chat."
        )

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.CHAT}

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text=(
                    "Put a login in front of the console and tell ai-os which one, under "
                    "Settings → Login."
                ),
                link="https://one.dash.cloudflare.com",
                details=[
                    "Cloudflare Access: an application for the console's address; ai-os "
                    "checks its signed token with the team domain and the application's AUD "
                    "tag.",
                    "Other proxies that sign a token (oauth2-proxy, Authentik, Pomerium) or "
                    "forward the address in a header work too.",
                    "The dev mode lets everyone in as one fixed person: only for a test on "
                    "your own machine.",
                ],
            ),
            SetupStep(
                text=(
                    "For each person: the address they sign in with as a web account under "
                    "Settings → Users."
                ),
                details=[
                    "They also need the chat permission (a role) to chat here; settings need"
                    " administrator.",
                ],
            ),
        ]

    @property
    def problems(self) -> list[SetupProblem]:
        return [
            SetupProblem(
                symptom='"Not allowed. Ask the owner to add your web account."',
                fix=(
                    "Add the exact address the person signs in with as a web account under "
                    "Settings → Users, with the chat permission."
                ),
            ),
            SetupProblem(
                symptom="The console works but has no chat.",
                fix="Switch the web console channel on, save, and restart ai-os.",
            ),
        ]

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        # The very instance the web server talks to.
        return self._channel
