from urllib.parse import parse_qs, urlsplit

import pytest

from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.oauth_client import OAuthClient
from aios.connectors.oauth_error import OAuthError
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from tests.agents.agent_world import AgentWorld
from tests.connectors.fake_oauth_server import FakeOAuthServer
from tests.fakes.fake_clock import FakeClock

REDIRECT = "https://ai-os.example.com/api/oauth/callback"


class _HttpAllowed(ConnectorAuthorizer):
    """The fake server speaks plain http; production insists on https."""

    def url_of(self, name: str) -> str | None:
        connector = self._connectors.get(name)
        return connector.config.get("url") if connector else None


async def _world(tmp_path):  # type: ignore[no-untyped-def]
    oauth = FakeOAuthServer()
    await oauth.server.start_server()
    w = AgentWorld(tmp_path)
    tokens: Collection[ConnectorToken] = Collection(
        CollectionDefinition(name="connector-tokens", entity=ConnectorToken),
        InMemoryDocumentStore(),
    )
    w.connectors._tokens = tokens  # the catalog the agent world built, now with tokens
    await w.connector_store.put(Connector(id="homey", config={"type": "http", "url": oauth.url}))
    clock = FakeClock()
    authorizer = _HttpAllowed(w.connectors, tokens, OAuthClient(), clock)
    return oauth, w, tokens, clock, authorizer


def _code_for(oauth: FakeOAuthServer, url: str) -> tuple[str, str]:
    query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert query["redirect_uri"] == REDIRECT and query["code_challenge_method"] == "S256"
    return query["state"], oauth.authorize(query["code_challenge"])


async def test_a_connector_is_signed_in_and_its_token_sent_and_renewed(tmp_path) -> None:
    oauth, w, tokens, clock, authorizer = await _world(tmp_path)
    try:
        url = await authorizer.start("homey", "alice", REDIRECT)
        assert url.startswith(f"{oauth.url}/oauth2/authorise?")
        state, code = _code_for(oauth, url)
        assert await authorizer.finish(state, code, "alice", "Alice") == "homey"
        token = tokens.get("homey")
        assert token is not None and token.signed_in_by == "Alice"
        assert w.connectors.servers()["homey"]["headers"]["Authorization"] == "Bearer access-1"
        with pytest.raises(OAuthError):  # the state is single-use
            await authorizer.finish(state, code, "alice", "Alice")
        await authorizer.renew_due()  # expires in 60 s, renewed 10 min ahead
        renewed = tokens.get("homey")
        assert renewed is not None and renewed.access_token == "access-r1"
        assert renewed.refresh_token == "refresh-1"  # kept when the server does not rotate it
        await authorizer.renew_due()  # now an hour left: nothing to do
        assert oauth.refreshes == 1
        await authorizer.sign_out("homey")
        assert "headers" not in w.connectors.servers()["homey"]
    finally:
        await oauth.server.close()


async def test_a_sign_in_cannot_be_finished_by_somebody_else(tmp_path) -> None:
    oauth, _, tokens, _, authorizer = await _world(tmp_path)
    try:
        state, code = _code_for(oauth, await authorizer.start("homey", "alice", REDIRECT))
        with pytest.raises(OAuthError):
            await authorizer.finish(state, code, "bob", "Bob")
        assert tokens.get("homey") is None
    finally:
        await oauth.server.close()


async def test_only_an_https_connector_can_be_signed_in_to(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.connector_store.put(Connector(id="local", config={"command": "npx"}))
    await w.connector_store.put(Connector(id="plain", config={"url": "http://x.example"}))
    tokens: Collection[ConnectorToken] = Collection(
        CollectionDefinition(name="t", entity=ConnectorToken), InMemoryDocumentStore()
    )
    authorizer = ConnectorAuthorizer(w.connectors, tokens, OAuthClient(), FakeClock())
    assert authorizer.url_of("local") is None and authorizer.url_of("plain") is None
    with pytest.raises(OAuthError):
        await authorizer.start("local", "alice", REDIRECT)
