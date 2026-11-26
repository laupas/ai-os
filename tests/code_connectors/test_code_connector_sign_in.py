from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from aios.connectors.code_connector_launcher import CodeConnectorLauncher
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connectors import TOKEN_ENV, CodeConnectors
from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_tokens import ConnectorTokens
from aios.connectors.oauth_client import OAuthClient
from aios.connectors.oauth_error import OAuthError
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.connectors.sign_in_mode import SignInMode
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.variables.secret_box import SecretBox
from tests.fakes.fake_clock import FakeClock

EXAMPLES = Path(__file__).parents[2] / "examples" / "code-connectors"
ALICE = User(id="alice", name="Alice")
BOB = User(id="bob", name="Bob")
OAUTH = {
    "authorization_endpoint": "https://login.example/authorize",
    "token_endpoint": "https://login.example/token",
    "client_id": "cid",
    "scopes": ["Mail.Read", "offline_access"],
}


def _token(user_id: str | None, access: str) -> ConnectorToken:
    return ConnectorToken(
        id=ConnectorTokens.key("hello-world", user_id),
        connector="hello-world",
        user_id=user_id,
        access_token=access,
        token_endpoint="https://login.example/token",
        client_id="cid",
    )


async def _catalog(tmp_path: Path, **connector: object) -> tuple[ConnectorCatalog, ConnectorTokens]:
    store: Collection[Connector] = Collection(
        CollectionDefinition(name="connectors", entity=Connector), InMemoryDocumentStore()
    )
    tokens = ConnectorTokens(
        Collection(
            CollectionDefinition(name="connector-tokens", entity=ConnectorToken),
            InMemoryDocumentStore(),
        ),
        SecretBox("a test key, long enough for one"),
    )
    code = CodeConnectors(CodeConnectorLibrary([EXAMPLES]), tmp_path / "state", lambda: "UTC")
    await store.put(Connector(id="hello-world", **connector))  # type: ignore[arg-type]
    return ConnectorCatalog(store, [], tokens=tokens, code=code), tokens


def _env(servers: dict) -> dict[str, str]:
    return servers["hello-world"]["env"]


async def test_a_per_user_code_connector_gets_only_the_turn_users_own_token(tmp_path) -> None:
    catalog, tokens = await _catalog(
        tmp_path, config={"code": "hello-world", "oauth": OAUTH}, sign_in=SignInMode.PER_USER
    )
    await tokens.put(_token("alice", "alices"))
    await tokens.put(_token(None, "shared"))
    env = _env(catalog.servers(ALICE))
    assert env[TOKEN_ENV] == "alices"
    assert TOKEN_ENV in env["AIOS_CONNECTOR_KEEP"].split(",")
    assert "oauth" not in catalog.servers(ALICE)["hello-world"]
    # Bob has not signed in and there is no fallback: left out, never the shared one.
    assert "hello-world" not in catalog.servers(BOB)
    assert catalog.unavailable_for(BOB) == ["hello-world"]


async def test_the_launcher_passes_the_token_on_and_nothing_else_of_ai_os(tmp_path) -> None:
    catalog, tokens = await _catalog(tmp_path, config={"code": "hello-world", "oauth": OAUTH})
    await tokens.put(_token(None, "shared"))
    env = _env(catalog.servers(None))
    kept = CodeConnectorLauncher.environment({**env, "AIOS_SECRETS_KEY": "secret"})
    assert kept[TOKEN_ENV] == "shared"
    assert "AIOS_SECRETS_KEY" not in kept


async def test_a_token_is_never_read_as_a_variable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOMETHING", "expanded")
    catalog, tokens = await _catalog(tmp_path, config={"code": "hello-world", "oauth": OAUTH})
    await tokens.put(_token(None, "${SOMETHING}"))
    assert _env(catalog.servers(None))[TOKEN_ENV] == "${SOMETHING}"


async def test_a_code_connector_without_an_oauth_client_gets_no_token(tmp_path) -> None:
    catalog, tokens = await _catalog(
        tmp_path, config={"code": "hello-world"}, sign_in=SignInMode.PER_USER
    )
    await tokens.put(_token("alice", "alices"))
    assert TOKEN_ENV not in _env(catalog.servers(ALICE))
    assert catalog.unavailable_for(BOB) == []


async def test_a_code_connector_is_signed_in_to_with_its_own_client(tmp_path) -> None:
    catalog, tokens = await _catalog(tmp_path, config={"code": "hello-world", "oauth": OAUTH})
    authorizer = ConnectorAuthorizer(catalog, tokens, OAuthClient(), FakeClock())
    assert authorizer.can_sign_in("hello-world")
    url = await authorizer.start("hello-world", "alice", "https://ai-os.example/cb", True)
    assert url.startswith("https://login.example/authorize?")
    query = parse_qs(urlsplit(url).query)
    assert query["client_id"] == ["cid"] and query["scope"] == ["Mail.Read offline_access"]


async def test_a_code_connector_without_a_client_cannot_be_signed_in_to(tmp_path) -> None:
    catalog, tokens = await _catalog(tmp_path, config={"code": "hello-world"})
    authorizer = ConnectorAuthorizer(catalog, tokens, OAuthClient(), FakeClock())
    assert not authorizer.can_sign_in("hello-world")
    with pytest.raises(OAuthError):
        await authorizer.start("hello-world", "alice", "https://ai-os.example/cb")
