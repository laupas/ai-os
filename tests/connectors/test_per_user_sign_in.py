from datetime import UTC, datetime

from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_tokens import ConnectorTokens
from aios.connectors.oauth_client import OAuthClient
from aios.engine.system_prompt_builder import SystemPromptBuilder
from aios.engine.turn_request import TurnRequest
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.connectors.sign_in_mode import SignInMode
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.memories.memory import Memory
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.variables.secret_box import SecretBox
from tests.agents.agent_world import AgentWorld
from tests.connectors.fake_oauth_server import FakeOAuthServer
from tests.connectors.test_connector_sign_in import REDIRECT, _code_for, _HttpAllowed
from tests.fakes.fake_clock import FakeClock

ALICE = User(id="alice", name="Alice")
BOB = User(id="bob", name="Bob")
NAME = "connector-tokens"


def _collection(store: InMemoryDocumentStore) -> Collection[ConnectorToken]:
    return Collection(CollectionDefinition(name=NAME, entity=ConnectorToken), store)


def _token(connector: str, user_id: str | None, access: str) -> ConnectorToken:
    return ConnectorToken(
        id=ConnectorTokens.key(connector, user_id),
        connector=connector,
        user_id=user_id,
        access_token=access,
        refresh_token=f"refresh-{access}",
        token_endpoint="https://x.example/token",
        client_id="cid",
        client_secret="client-secret",
    )


async def _world(tmp_path, **connector: object):  # type: ignore[no-untyped-def]
    w = AgentWorld(tmp_path)
    tokens = ConnectorTokens(
        _collection(InMemoryDocumentStore()), SecretBox(None, tmp_path / "key")
    )
    w.connectors._tokens = tokens
    await w.connector_store.put(
        Connector(id="gmail", config={"type": "http", "url": "https://gmail.example"}, **connector)
    )
    return w, tokens


def _bearer(servers: dict, name: str) -> str | None:
    return (servers.get(name, {}).get("headers") or {}).get("Authorization")


async def test_a_shared_connector_uses_the_one_account_for_everybody(tmp_path) -> None:
    w, tokens = await _world(tmp_path)
    await tokens.put(_token("gmail", None, "shared"))
    await tokens.put(_token("gmail", "bob", "bobs"))  # ignored while the connector is shared
    for user in (ALICE, BOB, None):
        assert _bearer(w.connectors.servers(user), "gmail") == "Bearer shared"
    assert w.connectors.unavailable_for(BOB) == []


async def test_per_user_each_user_gets_only_their_own_account(tmp_path) -> None:
    w, tokens = await _world(tmp_path, sign_in=SignInMode.PER_USER)
    await tokens.put(_token("gmail", "alice", "alices"))
    await tokens.put(_token("gmail", None, "shared"))
    assert _bearer(w.connectors.servers(ALICE), "gmail") == "Bearer alices"
    # Bob has none and there is no fallback: the connector is not given to the CLI at
    # all, so it does not try a sign-in of its own; the shared account is not used.
    assert "gmail" not in w.connectors.servers(BOB)
    assert w.connectors.unavailable_for(BOB) == ["gmail"]
    assert w.connectors.tool_prefixes() == ["mcp__aios__", "mcp__gmail__"]
    # A run without a user (none today) takes the shared account.
    assert _bearer(w.connectors.servers(None), "gmail") == "Bearer shared"


async def test_per_user_with_fallback_uses_the_shared_account_for_the_rest(tmp_path) -> None:
    w, tokens = await _world(tmp_path, sign_in=SignInMode.PER_USER, shared_fallback=True)
    assert w.connectors.unavailable_for(BOB) == ["gmail"]  # nothing to fall back on yet
    await tokens.put(_token("gmail", None, "shared"))
    await tokens.put(_token("gmail", "alice", "alices"))
    assert _bearer(w.connectors.servers(BOB), "gmail") == "Bearer shared"
    assert _bearer(w.connectors.servers(ALICE), "gmail") == "Bearer alices"


async def test_the_prompt_tells_the_agent_which_connectors_need_a_sign_in(tmp_path) -> None:
    w, _ = await _world(tmp_path, sign_in=SignInMode.PER_USER)
    memories: Collection[Memory] = Collection(
        CollectionDefinition(name="memories", entity=Memory), InMemoryDocumentStore()
    )
    prompts = SystemPromptBuilder(w.agents, FakeClock(), "Europe/Zurich", memories, w.connectors)
    now = datetime.now(UTC)
    request = TurnRequest(
        conversation=Conversation(id="c", created_at=now, updated_at=now),
        user=BOB,
        binding=ChannelBinding(channel="web", address="a", thread="t"),
        text="mails?",
    )
    prompt = prompts.build(request)
    assert "Bob has not signed in" in prompt and "gmail" in prompt and "Connectors" in prompt
    await w.connectors._tokens.put(_token("gmail", "bob", "bobs"))  # type: ignore[union-attr]
    assert "has not signed in" not in prompts.build(request)


async def test_each_user_signs_in_their_own_account_and_it_is_renewed(tmp_path) -> None:
    oauth = FakeOAuthServer()
    await oauth.server.start_server()
    try:
        w, tokens = await _world(tmp_path, sign_in=SignInMode.PER_USER)
        await w.connector_store.put(
            Connector(
                id="gmail",
                config={"type": "http", "url": oauth.url},
                sign_in=SignInMode.PER_USER,
            )
        )
        authorizer = _HttpAllowed(w.connectors, tokens, OAuthClient(), FakeClock())
        url = await authorizer.start("gmail", "bob", REDIRECT, own_account=True)
        state, code = _code_for(oauth, url)
        await authorizer.finish(state, code, "bob", "Bob")
        assert tokens.of_user("gmail", "bob") is not None
        assert tokens.shared("gmail") is None and tokens.of_user("gmail", "alice") is None
        assert tokens.users_signed_in("gmail") == 1
        await authorizer.renew_due()
        assert tokens.of_user("gmail", "bob").access_token == "access-r1"  # type: ignore[union-attr]
        await authorizer.sign_out("gmail", "bob")
        assert "gmail" not in w.connectors.servers(BOB)
    finally:
        await oauth.server.close()


async def test_tokens_are_encrypted_at_rest(tmp_path) -> None:
    store = InMemoryDocumentStore()
    tokens = ConnectorTokens(_collection(store), SecretBox(None, tmp_path / "key"))
    await tokens.put(_token("gmail", "bob", "secret-access"))
    raw = await store.get(NAME, "gmail.user.bob")
    assert raw is not None and raw["encrypted"] is True
    for field in ("access_token", "refresh_token", "client_secret"):
        assert "secret" not in raw[field] and "access" not in raw[field]
    token = tokens.of_user("gmail", "bob")
    assert token is not None and token.access_token == "secret-access"
    assert token.client_secret == "client-secret"
    # Under another key it cannot be read, and counts as not signed in.
    other = ConnectorTokens(_collection(store), SecretBox("another key", tmp_path / "x"))
    await other._tokens.load()
    assert other.of_user("gmail", "bob") is None


async def test_the_one_token_per_connector_becomes_the_shared_one(tmp_path) -> None:
    store = InMemoryDocumentStore()
    legacy = {
        "id": "homey",
        "access_token": "plain-access",
        "refresh_token": "plain-refresh",
        "token_endpoint": "https://homey.example/token",
        "client_id": "cid",
        "client_secret": "plain-secret",
        "auth_method": "client_secret_basic",
        "signed_in_by": "Alice",
    }
    await store.put(NAME, "homey", legacy)
    tokens = ConnectorTokens(_collection(store), SecretBox(None, tmp_path / "key"))
    await tokens._tokens.load()
    await tokens.migrate()
    assert [d["id"] for d in await store.list(NAME)] == ["homey.shared"]
    raw = await store.get(NAME, "homey.shared")
    assert raw is not None and raw["encrypted"] and raw["access_token"] != "plain-access"
    shared = tokens.shared("homey")
    assert shared is not None and shared.access_token == "plain-access"
    assert shared.refresh_token == "plain-refresh" and shared.signed_in_by == "Alice"
    await tokens.migrate()  # a second start changes nothing
    assert await store.get(NAME, "homey.shared") == raw


async def test_a_sign_in_lands_with_the_user_who_started_it(tmp_path) -> None:
    oauth = FakeOAuthServer()
    await oauth.server.start_server()
    try:
        w, tokens = await _world(tmp_path)
        await w.connector_store.put(Connector(id="h", config={"type": "http", "url": oauth.url}))
        authorizer: ConnectorAuthorizer = _HttpAllowed(
            w.connectors, tokens, OAuthClient(), FakeClock()
        )
        url = await authorizer.start("h", "alice", REDIRECT)  # the shared account
        state, code = _code_for(oauth, url)
        await authorizer.finish(state, code, "alice", "Alice")
        assert tokens.shared("h") is not None and tokens.of_user("h", "alice") is None
    finally:
        await oauth.server.close()
