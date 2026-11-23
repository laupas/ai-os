import asyncio
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from aios.agents.skill_catalog import SkillCatalog
from aios.approvals.file_root_guard import FileRootGuard
from aios.channels.channel_catalog import ChannelCatalog
from aios.channels.channel_directory import ChannelDirectory
from aios.channels.channel_values import ChannelValues
from aios.channels.slack.slack_channel_type import SlackChannelType
from aios.channels.web.web_channel import WebChannel
from aios.channels.web.web_channel_type import WebChannelType
from aios.channels.web.web_event_hub import WebEventHub
from aios.config.app_config_loader import AppConfigLoader
from aios.config.channel_config import ChannelConfig
from aios.config.live_app_config import LiveAppConfig
from aios.config.triggers_config import TriggersConfig
from aios.config.web_auth_config import WebAuthConfig
from aios.config.web_config import WebConfig
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connectors import CodeConnectors
from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.connectors.connector_tokens import ConnectorTokens
from aios.connectors.oauth_client import OAuthClient
from aios.conversations.conversation_deleter import ConversationDeleter
from aios.conversations.conversation_lock_manager import ConversationLockManager
from aios.conversations.gateway import Gateway
from aios.conversations.message_recorder import MessageRecorder
from aios.conversations.turn_canceller import TurnCanceller
from aios.engine.agent_engine import AgentEngine
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.memories.memory import Memory
from aios.entities.skills.skill import Skill
from aios.entities.triggers.trigger import Trigger
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.web_password import WebPassword
from aios.entities.variables.variable import Variable
from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.logs.log_reader import LogReader
from aios.messaging.mail.mail_channel_type import MailChannelType
from aios.messaging.sender_directory import SenderDirectory
from aios.messaging.signal.signal_channel_type import SignalChannelType
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.messaging.webhook.webhook_template import WebhookTemplate
from aios.storage.agent_access import AgentAccess
from aios.storage.collection import Collection
from aios.storage.collection_access_overrides import CollectionAccessOverrides
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.collection_definition import CollectionDefinition as Definition
from aios.triggers.trigger_runner import TriggerRunner
from aios.triggers.trigger_timing import TriggerTiming
from aios.variables.secret_box import SecretBox
from aios.variables.secret_extractor import SecretExtractor
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.login.chat_code_login import ChatCodeLogin
from aios.web.login.code_messenger import CodeMessenger
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.login_throttle import LoginThrottle
from aios.web.login.password_hasher import PasswordHasher
from aios.web.login.password_login import PasswordLogin
from aios.web.login.pick_login import PickLogin
from aios.web.login.sign_in_codes import SignInCodes
from aios.web.login.web_passwords import WebPasswords
from aios.web.login.web_sessions import WebSessions
from aios.web.restart_request import RestartRequest
from aios.web.routes.agent_routes import AgentRoutes
from aios.web.routes.approval_routes import ApprovalRoutes
from aios.web.routes.channel_settings_routes import ChannelSettingsRoutes
from aios.web.routes.claude_settings_routes import ClaudeSettingsRoutes
from aios.web.routes.connector_auth_routes import ConnectorAuthRoutes
from aios.web.routes.connector_routes import ConnectorRoutes
from aios.web.routes.conversation_routes import ConversationRoutes
from aios.web.routes.files_settings_routes import FilesSettingsRoutes
from aios.web.routes.history_routes import HistoryRoutes
from aios.web.routes.log_routes import LogRoutes
from aios.web.routes.login_routes import LoginRoutes
from aios.web.routes.memory_routes import MemoryRoutes
from aios.web.routes.password_routes import PasswordRoutes
from aios.web.routes.settings_routes import SettingsRoutes
from aios.web.routes.settings_section_routes import SettingsSectionRoutes
from aios.web.routes.skill_routes import SkillRoutes
from aios.web.routes.trigger_hook_routes import TriggerHookRoutes
from aios.web.routes.trigger_routes import TriggerRoutes
from aios.web.routes.variable_routes import VariableRoutes
from aios.web.routes.voice_routes import MAX_AUDIO_BYTES, VoiceRoutes
from aios.web.routes.voice_settings_routes import VoiceSettingsRoutes
from aios.web.routes.web_auth_settings_routes import WebAuthSettingsRoutes
from aios.web.routes.webhook_routes import WebhookRoutes
from aios.web.web_auth import WebAuth
from aios.web.web_identity import WebIdentity
from aios.web.web_identity_factory import WebIdentityFactory
from aios.web.web_server import WebServer
from tests.agents.agent_world import AgentWorld
from tests.config_repo.repo_world import RepoWorld
from tests.connectors.fake_connector_probe import FakeConnectorProbe
from tests.fakes.fake_channel import FakeChannel
from tests.fakes.fake_channel_type import FakeChannelType
from tests.fakes.fake_sender import FakeSender
from tests.fakes.fake_transcriber import FakeTranscriber
from tests.fakes.world import World
from tests.web.fake_claude_sign_in_check import FakeClaudeSignInCheck

EXAMPLES = Path(__file__).parents[2] / "examples" / "code-connectors"
ALICE = "alice@example.com"
BOB = "bob@example.com"


class HeaderIdentity(WebIdentity):
    """The test's stand-in for Access: the email is whatever `X-Test-Email` says."""

    async def email_of(self, request: web.Request) -> str | None:
        return request.headers.get("X-Test-Email")


class Console:
    """A web console over a `World`: Alice (owner) and Bob (member) both have
    a web account. Use as `async with Console(tmp_path) as c:`.

    With `auth` for the console's own login (pick, password), requests are told
    apart by the session cookie instead of `X-Test-Email`."""

    def __init__(
        self,
        tmp_path: Path,
        engine: AgentEngine | None = None,
        transcriber: FakeTranscriber | None = None,
        max_audio_bytes: int = MAX_AUDIO_BYTES,
        auth: WebAuthConfig | None = None,
    ) -> None:
        self.tmp_path = tmp_path
        self.auth = auth
        self.transcriber = transcriber or FakeTranscriber()
        self.voice = VoiceRoutes(self.transcriber, max_audio_bytes)
        self.world = World(engine=engine)
        self.hub = WebEventHub()
        self.channel = WebChannel(self.world.ids)
        self.slack = FakeChannel("slack")
        self.signal = FakeSender("signal")
        self.recorder = MessageRecorder(
            self.world.log, self.world.clock, self.world.ids, [self.hub]
        )
        self.restart = RestartRequest()
        self.sign_in_check = FakeClaudeSignInCheck({"sk-ant-good"})
        self.triggers_config = TriggersConfig()

    async def __aenter__(self) -> "Console":
        w = self.world
        await w.setup()
        await w.users.put(
            w.alice.model_copy(
                update={
                    "accounts": [*w.alice.accounts, ChannelAccount(channel="web", address=ALICE)]
                }
            )
        )
        await w.users.put(
            w.bob.model_copy(
                update={
                    "accounts": [*w.bob.accounts, ChannelAccount(channel="web", address=BOB)],
                    "role_ids": ["member"],
                }
            )
        )
        channels = ChannelDirectory(
            {"web": lambda: self.channel, "slack": lambda: self.slack}, ["web", "slack"]
        )
        canceller = TurnCanceller()
        gateway = Gateway(
            w.users,
            w.authorizer,
            w.resolver,
            self.recorder,
            ConversationLockManager(),
            canceller,
            w.engine,
            channels,
            w.approval_service,
            [self.hub],
        )
        deleter = ConversationDeleter(w.conversations, self.recorder, canceller)
        self.triggers: Collection[Trigger] = Collection(
            CollectionDefinition(name="triggers", entity=Trigger), w.store
        )
        self.memories: Collection[Memory] = Collection(
            CollectionDefinition(name="memories", entity=Memory), w.store
        )
        self._channel_task = asyncio.create_task(self.channel.start(gateway, w.approval_service))
        self.config_file = self.tmp_path / "config.yaml"
        self.config_file.write_text("channels: [web]\n")
        self.live_config = LiveAppConfig(AppConfigLoader(self.config_file).load())
        log_file = self.tmp_path / "aios.log"
        log_file.write_text("2099-01-01 00:00:00,000 ERROR aios.x boom\n")
        self.agent_world = AgentWorld(self.tmp_path)
        board = ConnectorStatusBoard(w.clock)
        self.skill_store: Collection[Skill] = Collection(
            CollectionDefinition(name="skills", entity=Skill), w.store
        )
        await self.skill_store.put(
            Skill(id="message-style", description="Voice.", content="Write as the user.\n")
        )
        self.skills = SkillCatalog(self.skill_store)
        aw = self.agent_world
        self.probe = FakeConnectorProbe(board)
        variables: Collection[Variable] = Collection(
            CollectionDefinition(name="variables", entity=Variable), w.store
        )
        box = SecretBox(None, self.tmp_path / "secrets.key")
        self.variables = VariableCatalog(variables, box, w.clock)
        self.variable_resolver = VariableResolver(variables, box, self.tmp_path / "variable-files")
        self.webhooks: Collection[WebhookDestination] = Collection(
            CollectionDefinition(name="webhooks", entity=WebhookDestination), w.store
        )
        self.tokens = ConnectorTokens(
            Collection(
                CollectionDefinition(name="connector-tokens", entity=ConnectorToken), w.store
            ),
            box,
        )
        aw.connectors._tokens = self.tokens
        authorizer = ConnectorAuthorizer(aw.connectors, self.tokens, OAuthClient(), w.clock)
        self.mountinfo = self.tmp_path / "mountinfo"
        self.vault = self.tmp_path / "vault"
        self.vault.mkdir()
        (self.tmp_path / "data").mkdir()
        self.mountinfo.write_text(
            f"1 0 0:1 / / rw - overlay overlay rw\n"
            f"2 1 0:2 / {self.vault} rw - fakeowner x rw\n"
            f"3 1 0:3 / {self.tmp_path / 'data'} rw - fakeowner x rw\n"
        )
        self.collection_overrides = CollectionAccessOverrides({})
        self.collection_overrides.apply(
            Definition(name="memories", entity=Memory, agent_access=AgentAccess.WRITE)
        )
        self.fake_type = FakeChannelType()
        self.channel_catalog = ChannelCatalog(
            [
                SlackChannelType(self.transcriber),
                WebChannelType(self.channel),
                SignalChannelType(),
                MailChannelType(),
                self.fake_type,
            ],
            {"web": ChannelConfig()},
            ChannelValues(self.variable_resolver),
        )
        self.repo_world = RepoWorld(self.tmp_path / "repo")
        self.repo_world.repo.init()
        console_users = ConsoleUsers(w.users, w.authorizer)
        self.passwords = WebPasswords(
            Collection(CollectionDefinition(name="web-passwords", entity=WebPassword), w.store),
            PasswordHasher(),
            w.clock,
        )
        self.sessions = WebSessions(box.derive_key("web-session"), w.clock)
        self.identities = WebIdentityFactory(
            self.sessions,
            console_users,
            [
                PickLogin(console_users),
                PasswordLogin(console_users, self.passwords, LoginThrottle(w.clock)),
                ChatCodeLogin(
                    console_users,
                    SignInCodes(w.clock),
                    CodeMessenger(
                        channels, SenderDirectory({"signal": lambda: self.signal}, ["signal"])
                    ),
                    LoginThrottle(w.clock),
                ),
            ],
        )
        login = self.identities.login_for(self.auth)
        identity = self.identities.create(WebConfig(auth=self.auth)) if login else HeaderIdentity()
        server = WebServer(
            WebAuth(identity, w.users, w.authorizer, login_page=login is not None),
            [
                LoginRoutes(login, self.sessions, 30),
                PasswordRoutes(self.passwords, w.users, w.authorizer),
                LogRoutes(LogReader(log_file), w.clock),
                ConversationRoutes(
                    w.conversations,
                    w.users,
                    w.resolver,
                    self.recorder,
                    self.channel,
                    self.hub,
                    deleter,
                    aw.agents,
                    w.approvals,
                ),
                AgentRoutes(
                    aw.agents,
                    self.skills,
                    aw.connectors,
                    board,
                    lambda: ["Task", "WebSearch", "WebFetch"],
                ),
                SkillRoutes(self.skills, aw.agents),
                HistoryRoutes(self.repo_world.store, self.repo_world.collections),
                VariableRoutes(self.variables, self.variable_resolver, aw.connectors),
                ConnectorAuthRoutes(authorizer, aw.connectors, None),
                ConnectorRoutes(
                    aw.connector_store,
                    aw.connectors,
                    board,
                    aw.agents,
                    authorizer=authorizer,
                    tokens=self.tokens,
                    resolver=self.variable_resolver,
                    probe=self.probe,
                    secrets=SecretExtractor(self.variables, self.variable_resolver),
                    code=CodeConnectors(
                        CodeConnectorLibrary([EXAMPLES]),
                        self.tmp_path / "connector-state",
                        lambda: "UTC",
                        self.variable_resolver,
                    ),
                    variables=self.variables,
                ),
                SettingsRoutes(
                    AiosYamlFile(self.config_file, live=self.live_config),
                    self.live_config,
                    w.users,
                    w.roles,
                    w.ids,
                    self.restart,
                ),
                SettingsSectionRoutes(AiosYamlFile(self.config_file), self.collection_overrides),
                VoiceSettingsRoutes(self.variables, self.variable_resolver),
                WebAuthSettingsRoutes(AiosYamlFile(self.config_file), self.identities),
                FilesSettingsRoutes(
                    AiosYamlFile(self.config_file),
                    FileRootGuard([self.tmp_path / "data"]),
                    self.mountinfo,
                ),
                ChannelSettingsRoutes(
                    AiosYamlFile(self.config_file),
                    self.channel_catalog,
                    ChannelValues(self.variable_resolver),
                    self.variables,
                    ["web"],
                ),
                ClaudeSettingsRoutes(
                    AiosYamlFile(self.config_file, live=self.live_config),
                    self.variables,
                    self.variable_resolver,
                    lambda: self.live_config.current().agent.auth,
                    self.sign_in_check,
                ),
                WebhookRoutes(
                    self.webhooks,
                    WebhookPoster(WebhookTemplate(self.variable_resolver), enabled=True),
                    SecretExtractor(self.variables, self.variable_resolver),
                ),
                MemoryRoutes(self.memories, w.users, w.ids, w.clock),
                self.voice,
                ApprovalRoutes(w.approvals, w.approval_service),
                TriggerRoutes(
                    self.triggers,
                    TriggerTiming(),
                    TriggerRunner(w.users, channels, gateway),
                    w.clock,
                    w.ids,
                    w.users,
                    aw.agents,
                ),
                TriggerHookRoutes(
                    self.triggers,
                    TriggerRunner(w.users, channels, gateway),
                    w.clock,
                    lambda: self.triggers_config,
                ),
            ],
            self.restart,
            port=0,
            static_dir=self._built_page(),
        )
        self.client = TestClient(TestServer(server.build()))
        await self.client.start_server()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.client.close()
        self._channel_task.cancel()

    def _built_page(self) -> Path:
        static = self.tmp_path / "static"
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text('<script src="/static/assets/index-abc123.js"></script>')
        (static / "assets" / "index-abc123.js").write_text("console.log('ai-os')")
        return static

    def headers(self, email: str | None, write: bool = False) -> dict[str, str]:
        headers = {"X-Test-Email": email} if email else {}
        if write:
            headers["X-Aios"] = "1"
        return headers
