from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.channels.message_chunker import MessageChunker
from aios.channels.setup_step import SetupStep
from aios.channels.teams.teams_bot import TeamsBot
from aios.channels.teams.teams_cards import TeamsCards
from aios.channels.teams.teams_channel import TeamsChannel
from aios.channels.teams.teams_emoji import TeamsEmoji
from aios.channels.teams.teams_threads import TeamsThreads
from aios.channels.teams.teams_voice_notes import TeamsVoiceNotes
from aios.transcription.transcriber import Transcriber
from aios.variables.variable_field import VariableField

APP_ID = "TEAMS_APP_ID"
PASSWORD = "TEAMS_APP_PASSWORD"
TENANT = "TEAMS_TENANT_ID"


class TeamsChannelType(ChannelType):
    """Microsoft Teams in Socket Mode: a bot from the Teams Developer Portal with
    its client id, a client secret, and the tenant it lives in."""

    def __init__(self, transcriber: Transcriber, chunk_size: int = 12000) -> None:
        self._transcriber = transcriber
        self._chunk_size = chunk_size

    @property
    def name(self) -> str:
        return "teams"

    @property
    def title(self) -> str:
        return "Microsoft Teams"

    @property
    def description(self) -> str:
        return (
            "Chat in Teams chats and channel threads, with progress, a stop button and "
            "approval buttons. Uses Socket Mode (a preview), so no public address is needed: "
            "switch it on for the bot in the Teams Developer Portal."
        )

    @property
    def capabilities(self) -> set[ChannelCapability]:
        return {ChannelCapability.CHAT}

    @property
    def fields(self) -> list[VariableField]:
        return [
            VariableField(
                variable=APP_ID,
                label="Bot id",
                hint="Developer Portal → Tools → Bot management: the bot's id.",
                secret=False,
                placeholder="00000000-0000-0000-0000-000000000000",
            ),
            VariableField(
                variable=PASSWORD,
                label="Client secret",
                hint="Bot management → the bot → Client secrets → Add a client secret.",
            ),
            VariableField(
                variable=TENANT,
                label="Tenant id",
                hint="Your Microsoft 365 organisation's id (Entra admin center → Overview).",
                secret=False,
                placeholder="00000000-0000-0000-0000-000000000000",
            ),
        ]

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text="Teams Developer Portal → Tools → Bot management → New bot. Its id is the bot"
                " id; add a client secret there.",
                link="https://dev.teams.microsoft.com",
            ),
            SetupStep(
                text="The bot → Configure → Delivery method → Socket mode → Save. A preview, only "
                "for newly created bots.",
            ),
            SetupStep(
                text="Apps → New app → App features → Bot: pick the bot, scopes personal, team and"
                " group chat. Then Preview in Teams, or publish it to your organisation.",
                link="https://dev.teams.microsoft.com/apps",
            ),
            SetupStep(
                text="The tenant id is on the Overview of the Microsoft Entra admin center.",
                link="https://entra.microsoft.com",
            ),
            SetupStep(
                text="For each person: their Microsoft Entra object id (Entra admin center → Users"
                " → the person) as a teams account under Users.",
            ),
        ]

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        app_id, password, tenant = values[APP_ID], values[PASSWORD], values[TENANT]
        if not app_id or not password or not tenant:
            raise RuntimeError(f"Teams needs {APP_ID}, {PASSWORD} and {TENANT}")
        return TeamsChannel(
            tenant_id=tenant,
            bot=TeamsBot(app_id=app_id, password=password, tenant_id=tenant),
            threads=TeamsThreads(),
            cards=TeamsCards(),
            emoji=TeamsEmoji(),
            chunker=MessageChunker(size=self._chunk_size),
            voice_notes=TeamsVoiceNotes(transcriber=self._transcriber),
        )

    async def check(self, values: dict[str, str | None]) -> ChannelCheckResult:
        app_id, password, tenant = values[APP_ID], values[PASSWORD], values[TENANT]
        if not app_id or not password or not tenant:
            return ChannelCheckResult(ok=False, detail="bot id, secret and tenant id are needed")
        try:
            detail = await TeamsBot(app_id=app_id, password=password, tenant_id=tenant).check()
        except Exception as exc:
            return ChannelCheckResult(ok=False, detail=str(exc))
        return ChannelCheckResult(ok=True, detail=detail)
