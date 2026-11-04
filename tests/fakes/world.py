from aios.approvals.approval_service import ApprovalService
from aios.channels.channel_directory import ChannelDirectory
from aios.common.id_generator import IdGenerator
from aios.conversations.conversation_lock_manager import ConversationLockManager
from aios.conversations.conversation_resolver import ConversationResolver
from aios.conversations.gateway import Gateway
from aios.conversations.message_recorder import MessageRecorder
from aios.conversations.turn_canceller import TurnCanceller
from aios.engine.agent_engine import AgentEngine
from aios.entities.approvals.approval import Approval
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.agent_access import AgentAccess
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.collection_registry import CollectionRegistry
from aios.storage.in_memory_append_log import InMemoryAppendLog
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.users.authorizer import Authorizer
from aios.users.default_roles import DefaultRoles
from tests.fakes.fake_channel import FakeChannel
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_engine import FakeEngine


class World:
    """The real core objects over in-memory storage, with fakes at the edges.

    Users: Alice (owner, account fake:alice) and Bob (no role, fake:bob).
    """

    def __init__(self, engine: AgentEngine | None = None, timeout_seconds: float = 5) -> None:
        self.store = InMemoryDocumentStore()
        self.log = InMemoryAppendLog()
        self.clock = FakeClock()
        self.ids = IdGenerator()
        self.users: Collection[User] = Collection(
            CollectionDefinition(name="users", entity=User, agent_access=AgentAccess.WRITE),
            self.store,
        )
        self.roles: Collection[Role] = Collection(
            CollectionDefinition(name="roles", entity=Role), self.store
        )
        self.conversations: Collection[Conversation] = Collection(
            CollectionDefinition(name="conversations", entity=Conversation), self.store
        )
        self.approvals: Collection[Approval] = Collection(
            CollectionDefinition(name="approvals", entity=Approval), self.store
        )
        self.registry = CollectionRegistry(
            [self.users, self.roles, self.conversations, self.approvals]
        )
        self.authorizer = Authorizer(self.roles)
        self.channel = FakeChannel()
        self.channels = ChannelDirectory({"fake": lambda: self.channel}, ["fake"])
        self.approval_service = ApprovalService(
            self.approvals,
            self.users,
            self.authorizer,
            self.channels,
            self.clock,
            self.ids,
            timeout_seconds,
        )
        self.resolver = ConversationResolver(self.conversations, self.clock, self.ids)
        self.recorder = MessageRecorder(self.log, self.clock, self.ids)
        self.engine = engine or FakeEngine()
        self.gateway = Gateway(
            self.users,
            self.authorizer,
            self.resolver,
            self.recorder,
            ConversationLockManager(),
            TurnCanceller(),
            self.engine,
            self.channels,
            self.approval_service,
        )
        self.alice = User(
            id="alice",
            name="Alice",
            accounts=[
                ChannelAccount(channel="fake", address="alice"),
                ChannelAccount(channel="signal", address="+41000000001"),
            ],
            role_ids=[DefaultRoles.OWNER],
        )
        self.bob = User(
            id="bob",
            name="Bob",
            aliases=["Edi"],
            accounts=[
                ChannelAccount(channel="fake", address="bob"),
                ChannelAccount(channel="signal", address="+41000000002"),
            ],
        )

    async def setup(self) -> "World":
        for role in DefaultRoles().all():
            await self.roles.put(role)
        await self.users.put(self.alice)
        await self.users.put(self.bob)
        return self
