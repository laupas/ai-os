from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_check_result import ChannelCheckResult
from aios.channels.channel_type import ChannelType
from aios.channels.message_channel import MessageChannel
from aios.channels.message_chunker import MessageChunker
from aios.channels.setup_problem import SetupProblem
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
CHAT_THREADS = "TEAMS_CHAT_THREADS"
ON = {"on", "true", "yes", "1"}


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
                hint="Developer Portal → Tools → Bot management: the bot's id, not the Teams app's "
                "App ID.",
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
                hint="Your Microsoft 365 organisation's id: Entra admin center → Overview.",
                secret=False,
                placeholder="00000000-0000-0000-0000-000000000000",
            ),
            VariableField(
                variable=CHAT_THREADS,
                label="Threads in chats",
                hint="on: each message at the top of a chat starts a conversation, answered in its "
                'thread, like Slack. Needs "Reply in thread" in your Teams chats. Empty: the chat '
                "is one conversation until /new.",
                secret=False,
                required=False,
                placeholder="on",
            ),
        ]

    @property
    def setup(self) -> list[SetupStep]:
        return [
            SetupStep(
                text=(
                    "Create a bot: Teams Developer Portal → Tools (pencil icon) → Bot management → "
                    "New bot, with a name such as ai-os."
                ),
                link="https://dev.teams.microsoft.com",
                details=[
                    "The portal opens in the organisation you sign in with; the bot, the app and "
                    "its users all live there.",
                    "The bot's id in the Bot management list is the Bot id below. It is not the "
                    "App ID of the Teams app made in a later step.",
                ],
            ),
            SetupStep(
                text=(
                    "Client secret: Bot management → the bot → Client secrets → Add a client secret"
                    " for your bot."
                ),
                details=[
                    "Copy the value at once: it is shown only this one time. Paste it into Client "
                    "secret below, nowhere else.",
                    "A secret expires; when Test reports a wrong or expired secret, add a new one "
                    "here and enter it again.",
                ],
            ),
            SetupStep(
                text="Socket Mode: the bot → Configure → Delivery method → Socket mode → Save.",
                details=[
                    "With Socket Mode ai-os dials out to Teams, so no public address and no "
                    "messaging endpoint are needed.",
                    "It is a Microsoft preview and only for newly created bots. Test below says "
                    "whether it is on.",
                    "If saving fails with \"Couldn't find this bot's Microsoft Entra app\", that "
                    "is a known Microsoft bug: wait for the fix, or create the bot anew.",
                ],
            ),
            SetupStep(
                text=(
                    "Teams app: Apps → New app. Under Configure → Basic information fill in the "
                    "developer name, website, privacy and terms of use addresses (any https:// "
                    "address), the short and the full description."
                ),
                link="https://dev.teams.microsoft.com/apps",
                details=[
                    'Empty addresses or descriptions stop the app with "Schema validation failed".',
                    "The hint about supportsChannelFeatures=tier1 is only a recommendation for "
                    "private and shared channels; it can be ignored.",
                ],
            ),
            SetupStep(
                text=(
                    "Add the bot to the app: Configure → App features → Bot → Select an existing "
                    "bot → the bot from step 1, with the scopes Personal, Team and Group chat. "
                    "Save."
                ),
                details=[
                    'For voice notes in the personal chat, add "supportsFiles": true to the bot in'
                    " Configure → App package editor → manifest.json.",
                ],
            ),
            SetupStep(
                text=(
                    "Enter the bot id, the client secret and the tenant id below, then Test. Green "
                    "means the bot signs in and Teams offers it a socket. Then switch the channel "
                    "on, save, and restart ai-os."
                ),
                link="https://entra.microsoft.com",
                details=[
                    "The tenant id is on the Overview page of the Microsoft Entra admin center.",
                    "With the channel on, ai-os connects to Teams by itself; installing the app "
                    "comes next.",
                ],
            ),
            SetupStep(
                text=(
                    "Install the app only for yourself: in the app, Preview in Teams → Add. If "
                    'Teams answers "Permissions needed", custom apps are not allowed for your '
                    "account yet."
                ),
                link="https://admin.teams.microsoft.com",
                details=[
                    "Allow it just for some people: Teams admin center → Teams apps → Setup "
                    "policies → Add a policy with Upload custom apps on, and assign it to them "
                    "only.",
                    'Teams apps → Manage apps → Actions → Org-wide app settings must have "Let '
                    'users interact with custom apps" on.',
                    "Policy changes can take hours. Without waiting: Publish → Publish to org, "
                    "approve it in Teams admin center → Manage apps, and make it available to "
                    "specific users only.",
                    "Being a global administrator does not skip these policies; they apply to "
                    "every account.",
                ],
            ),
            SetupStep(
                text=(
                    "For each person: their Microsoft Entra object id, in lower case, as a teams "
                    "account under Settings → Users."
                ),
                link="https://developer.microsoft.com/graph/graph-explorer",
                details=[
                    "In Graph Explorer, signed in as the person, GET "
                    "https://graph.microsoft.com/v1.0/me: the id is the object id.",
                    "Or Entra admin center → Users → the person → Overview → Object ID.",
                    'Someone who is not set up yet gets "Sorry, you are not allowed to use ai-os";'
                    " the log shows their object id.",
                ],
            ),
            SetupStep(
                text=(
                    "Using it: the personal chat with the bot is one conversation until you write "
                    "/new. In a team, @mention the bot in a new post: each post is its own "
                    "conversation, replies need no mention."
                ),
                details=[
                    "Reply with quote on an earlier message in a chat goes back to that "
                    "message's conversation, e.g. a scheduled run's; the chat stays there.",
                    "With Threads in chats on, a chat works like a team: each message at the top "
                    "is its own conversation, answered in its thread, and you continue it with "
                    "Reply in thread. Only switch it on if Teams offers Reply in thread on chat "
                    "messages; otherwise every message starts afresh.",
                    "Schedules reach a person in their personal chat with the bot, besides their "
                    "other channels, once the app is installed for them.",
                    "All Teams conversations also show in this console.",
                ],
            ),
        ]

    @property
    def problems(self) -> list[SetupProblem]:
        return [
            SetupProblem(
                symptom='Test: "unauthorized_client" or "was not found in the directory".',
                fix=(
                    "The Bot id is not the bot's: most often it is the App ID of the Teams app. "
                    "Take the id from Tools → Bot management."
                ),
            ),
            SetupProblem(
                symptom='Test: the secret is wrong or has expired ("invalid_client").',
                fix=(
                    "Add a new client secret to the bot and enter it again; the old value cannot be"
                    " shown again."
                ),
            ),
            SetupProblem(
                symptom="Test: the bot signed in, but Socket Mode is not on for it.",
                fix=(
                    "Bot management → the bot → Configure → Delivery method → Socket mode → Save, "
                    "then wait about a minute."
                ),
            ),
            SetupProblem(
                symptom=(
                    'Teams: "Permissions needed. Ask your IT admin to add … to this '
                    'team/chat/meeting."'
                ),
                fix=(
                    "Custom apps are blocked for the account: see step 7, or publish the app to the"
                    " organisation for specific users only."
                ),
            ),
            SetupProblem(
                symptom='The bot answers "Sorry, you are not allowed to use ai-os".',
                fix=(
                    "Add the person's Entra object id, in lower case, as a teams account under "
                    "Settings → Users; they need the chat permission."
                ),
            ),
            SetupProblem(
                symptom="The bot does not answer at all.",
                fix=(
                    "Check that the channel is on and ai-os was restarted, and that the person "
                    "installed the app. In a team, the bot only reacts to an @mention."
                ),
            ),
        ]

    def create_channel(self, values: dict[str, str | None]) -> MessageChannel:
        app_id, password, tenant = values[APP_ID], values[PASSWORD], values[TENANT]
        if not app_id or not password or not tenant:
            raise RuntimeError(f"Teams needs {APP_ID}, {PASSWORD} and {TENANT}")
        return TeamsChannel(
            tenant_id=tenant,
            bot=TeamsBot(app_id=app_id, password=password, tenant_id=tenant),
            threads=TeamsThreads(in_chats=(values.get(CHAT_THREADS) or "").strip().lower() in ON),
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
