import asyncio
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from aios.agents.skill_catalog import SkillCatalog
from aios.channels.channel_directory import ChannelDirectory
from aios.channels.web.web_channel import WebChannel
from aios.channels.web.web_event_hub import WebEventHub
from aios.config.connector_override import ConnectorOverride
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
from aios.entities.schedules.schedule import Schedule
from aios.entities.skills.skill import Skill
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.variables.variable import Variable
from aios.logs.log_reader import LogReader
from aios.scheduler.schedule_runner import ScheduleRunner
from aios.scheduler.schedule_timing import ScheduleTiming
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.variables.secret_box import SecretBox
from aios.variables.secret_extractor import SecretExtractor
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from aios.web.restart_request import RestartRequest
from aios.web.routes.agent_routes import AgentRoutes
from aios.web.routes.connector_auth_routes import ConnectorAuthRoutes
from aios.web.routes.connector_routes import ConnectorRoutes
from aios.web.routes.conversation_routes import ConversationRoutes
from aios.web.routes.history_routes import HistoryRoutes
from aios.web.routes.log_routes import LogRoutes
from aios.web.routes.schedule_routes import ScheduleRoutes
from aios.web.routes.settings_routes import SettingsRoutes
from aios.web.routes.skill_routes import SkillRoutes
from aios.web.routes.variable_routes import VariableRoutes
from aios.web.web_auth import WebAuth
from aios.web.web_identity import WebIdentity
from aios.web.web_server import WebServer
from tests.agents.agent_world import AgentWorld
from tests.config_repo.repo_world import RepoWorld
from tests.connectors.fake_connector_probe import FakeConnectorProbe
from tests.fakes.fake_channel import FakeChannel
from tests.fakes.world import World

ALICE = "alice@example.com"
BOB = "bob@example.com"


class HeaderIdentity(WebIdentity):
    """The test's stand-in for Access: the email is whatever `X-Test-Email` says."""

    async def email_of(self, request: web.Request) -> str | None:
        return request.headers.get("X-Test-Email")


class Console:
    """A web console over a `World`: Alice (owner) and Bob (member) both have
    a web account. Use as `async with Console(tmp_path) as c:`."""

    def __init__(self, tmp_path: Path, engine: AgentEngine | None = None) -> None:
        self.tmp_path = tmp_path
        self.world = World(engine=engine)
        self.hub = WebEventHub()
        self.channel = WebChannel(self.world.ids)
        self.slack = FakeChannel("slack")
        self.recorder = MessageRecorder(
            self.world.log, self.world.clock, self.world.ids, [self.hub]
        )
        self.restart = RestartRequest()

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
        self.schedules: Collection[Schedule] = Collection(
            CollectionDefinition(name="schedules", entity=Schedule), w.store
        )
        self._channel_task = asyncio.create_task(self.channel.start(gateway, w.approval_service))
        self.config_file = self.tmp_path / "config.yaml"
        self.config_file.write_text("channels: [web]\n")
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
        self.tokens = ConnectorTokens(
            Collection(
                CollectionDefinition(name="connector-tokens", entity=ConnectorToken), w.store
            ),
            box,
        )
        aw.connectors._tokens = self.tokens
        authorizer = ConnectorAuthorizer(aw.connectors, self.tokens, OAuthClient(), w.clock)
        self.repo_world = RepoWorld(self.tmp_path / "repo")
        self.repo_world.repo.init()
        server = WebServer(
            WebAuth(HeaderIdentity(), w.users, w.authorizer),
            [
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
                    ["Task", "WebSearch", "WebFetch"],
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
                        CodeConnectorLibrary([Path(__file__).parents[2] / "connectors"]),
                        {"crypto": ConnectorOverride(settings={"max_chf_per_day": 300})},
                        self.tmp_path / "connector-state",
                        "UTC",
                    ),
                ),
                SettingsRoutes(self.config_file, w.users, w.roles, w.ids, self.restart),
                ScheduleRoutes(
                    self.schedules,
                    ScheduleTiming(),
                    ScheduleRunner(w.users, channels, gateway),
                    w.clock,
                    w.ids,
                    w.users,
                    aw.agents,
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
