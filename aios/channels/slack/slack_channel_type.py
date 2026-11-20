from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.channels.slack.markdown_to_mrkdwn import MarkdownToMrkdwn
from aios.channels.slack.message_chunker import MessageChunker
from aios.channels.slack.slack_blocks import SlackBlocks
from aios.channels.slack.slack_channel import SlackChannel
from aios.channels.slack.slack_voice_notes import SlackVoiceNotes
from aios.transcription.transcriber import Transcriber
from aios.variables.variable_field import VariableField

BOT = "SLACK_BOT_TOKEN"
APP = "SLACK_APP_TOKEN"


class SlackChannelType(ChannelType):
    """Slack over Socket Mode: a Slack app with a bot token and an app-level token."""

    def __init__(self, transcriber: Transcriber, chunk_size: int = 3500) -> None:
        self._transcriber = transcriber
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

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        bot = values[BOT] or ""
        return SlackChannel(
            bot_token=bot,
            app_token=values[APP],
            blocks=SlackBlocks(),
            converter=MarkdownToMrkdwn(),
            chunker=MessageChunker(size=self._chunk_size),
            voice_notes=SlackVoiceNotes(bot_token=bot, transcriber=self._transcriber),
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
