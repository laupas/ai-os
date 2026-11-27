from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.channels.message_chunker import MessageChunker
from aios.channels.setup_problem import SetupProblem
from aios.channels.setup_step import SetupStep
from aios.channels.slack.markdown_to_mrkdwn import MarkdownToMrkdwn
from aios.channels.slack.slack_blocks import SlackBlocks
from aios.channels.slack.slack_channel import SlackChannel
from aios.channels.slack.slack_voice_notes import SlackVoiceNotes
from aios.transcription.transcriber import Transcriber
from aios.users.voice_gate import VoiceGate
from aios.variables.variable_field import VariableField

BOT = "SLACK_BOT_TOKEN"
APP = "SLACK_APP_TOKEN"


class SlackChannelType(ChannelType):
    """Slack over Socket Mode: a Slack app with a bot token and an app-level token."""

    def __init__(
        self, transcriber: Transcriber, voice_gate: VoiceGate, chunk_size: int = 3500
    ) -> None:
        self._transcriber = transcriber
        self._voice_gate = voice_gate
        self._chunk_size = chunk_size

    @property
    def name(self) -> str:
        return "slack"

    @property
    def title(self) -> str:
        return "Slack"

    @property
    def description(self) -> str:
        return (
            "Chat in Slack threads, with progress, a stop button and approval buttons. "
            "Needs a Slack app with Socket Mode on, so no public address is needed."
        )

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.CHAT}

    @property
    def fields(self) -> list[VariableField]:
        return [
            VariableField(
                variable=BOT,
                label="Bot token",
                hint="OAuth & Permissions → Bot User OAuth Token.",
                placeholder="xoxb-…",
            ),
            VariableField(
                variable=APP,
                label="App-level token",
                hint="Basic Information → App-Level Tokens, with the connections:write scope.",
                placeholder="xapp-…",
            ),
        ]

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text=(
                    "Create a Slack app: Create New App → From scratch, with a name such as "
                    "ai-os, in your workspace."
                ),
                link="https://api.slack.com/apps",
                details=[
                    "Use one app per ai-os installation: two programs connected with the "
                    "same app split the messages between them.",
                ],
            ),
            SetupStep(
                text=(
                    "Socket Mode: Settings → Socket Mode → on. Then Basic Information → "
                    "App-Level Tokens → Generate, with the scope connections:write."
                ),
                details=[
                    "The token starts with xapp-; it is the App-level token below.",
                    "With Socket Mode ai-os dials out to Slack, so no public address is needed.",
                ],
            ),
            SetupStep(
                text=(
                    "Permissions: OAuth & Permissions → Bot Token Scopes: chat:write, "
                    "im:history, channels:history, groups:history, mpim:history. Then Install"
                    " to Workspace."
                ),
                details=[
                    "The Bot User OAuth Token (xoxb-) is the Bot token below.",
                    "Optional: chat:write.customize and users:read, so words a person typed "
                    "on another channel show with their name and picture rather than a "
                    "label.",
                    "Optional: files:write, so documents agents make (artifacts) arrive "
                    "as files in the thread rather than as a link.",
                    "After adding a scope, install the app again (Reinstall to Workspace), "
                    "or the token keeps the old scopes.",
                ],
            ),
            SetupStep(
                text=(
                    "Events and buttons: Event Subscriptions → on, bot events message.im, "
                    "message.channels, message.groups, message.mpim. Interactivity & "
                    "Shortcuts → on."
                ),
                details=[
                    "Without Interactivity the Stop and approval buttons do nothing.",
                    'App Home → Show Tabs → Messages Tab on, with "Allow users to send Slash'
                    ' commands and messages from the messages tab", or people cannot write '
                    "to the app.",
                ],
            ),
            SetupStep(
                text=(
                    "Enter both tokens below and Test, then switch the channel on, save, and "
                    "restart ai-os."
                ),
                details=[
                    "Green means the bot token signs in and the app-level token may open a "
                    "connection.",
                ],
            ),
            SetupStep(
                text=(
                    "For each person: their Slack member id as a slack account under Settings"
                    " → Users."
                ),
                details=[
                    "In Slack: their profile → ⋮ (more) → Copy member ID. It looks like "
                    "U0123ABCDEF.",
                ],
            ),
            SetupStep(
                text=(
                    "Using it: every message to the app in a direct message starts its own "
                    "thread and conversation. In a channel, invite the app (/invite @ai-os) "
                    "and mention it; replies in the thread need no mention."
                ),
                details=[
                    "Slack conversations also show in this console.",
                ],
            ),
        ]

    @property
    def problems(self) -> list[SetupProblem]:
        return [
            SetupProblem(
                symptom='Test: "bot token: invalid_auth" or "not_authed".',
                fix=(
                    "The bot token is wrong or was revoked: copy the Bot User OAuth Token "
                    "(xoxb-) again from OAuth & Permissions."
                ),
            ),
            SetupProblem(
                symptom='Test: "app-level token: …".',
                fix=(
                    "Use an app-level token (xapp-) with the scope connections:write, and "
                    "check that Socket Mode is on."
                ),
            ),
            SetupProblem(
                symptom='Slack: "Sending messages to this app has been turned off".',
                fix="App Home → Show Tabs → Messages Tab on, with messages allowed.",
            ),
            SetupProblem(
                symptom="The app stays silent in a channel.",
                fix=(
                    "Invite it to the channel and mention it; check the bot events "
                    "message.channels (and message.groups for private channels)."
                ),
            ),
            SetupProblem(
                symptom="Stop and approval buttons do nothing.",
                fix="Interactivity & Shortcuts → on.",
            ),
            SetupProblem(
                symptom='The app answers "Sorry, you are not allowed to use ai-os".',
                fix=(
                    "Add the person's member id as a slack account under Settings → Users; "
                    "they need the chat permission."
                ),
            ),
        ]

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        bot = values[BOT] or ""
        return SlackChannel(
            bot_token=bot,
            app_token=values[APP],
            blocks=SlackBlocks(),
            converter=MarkdownToMrkdwn(),
            chunker=MessageChunker(size=self._chunk_size),
            voice_notes=SlackVoiceNotes(
                bot_token=bot, transcriber=self._transcriber, gate=self._voice_gate
            ),
        )

    async def check(self, values: dict[str, str | None]) -> ChannelCheckResult:
        if not values[BOT] or not values[APP]:
            return ChannelCheckResult(ok=False, detail="both tokens are needed")
        try:
            who = await AsyncWebClient(token=values[BOT]).auth_test()
        except SlackApiError as exc:
            return ChannelCheckResult(ok=False, detail=f"bot token: {exc.response['error']}")
        try:
            await AsyncWebClient().apps_connections_open(app_token=values[APP])
        except SlackApiError as exc:
            return ChannelCheckResult(ok=False, detail=f"app-level token: {exc.response['error']}")
        return ChannelCheckResult(
            ok=True, detail=f"signed in as @{who['user']} in {who.get('team', 'the workspace')}"
        )
