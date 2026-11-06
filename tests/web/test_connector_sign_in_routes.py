from urllib.parse import parse_qs, urlsplit

from aios.connectors.connector_tokens import ConnectorTokens
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.connectors.sign_in_mode import SignInMode
from tests.web.console import ALICE, BOB, Console

OAUTH = {
    "authorization_endpoint": "https://accounts.example.com/auth",
    "token_endpoint": "https://accounts.example.com/token",
    "client_id": "cid",
}


async def _connectors(c: Console) -> None:
    store = c.agent_world.connector_store
    url = "https://mcp.example.com/mcp"
    await store.put(
        Connector(
            id="mail",
            description="Mail",
            config={"type": "http", "url": url, "oauth": OAUTH},
            sign_in=SignInMode.PER_USER,
        )
    )
    await store.put(Connector(id="homey", config={"type": "http", "url": url, "oauth": OAUTH}))
    await store.put(Connector(id="local", config={"command": "npx"}))


def _token(connector: str, user_id: str | None, by: str) -> ConnectorToken:
    return ConnectorToken(
        id=ConnectorTokens.key(connector, user_id),
        connector=connector,
        user_id=user_id,
        access_token="secret-access",
        token_endpoint="https://x/token",
        client_id="cid",
        signed_in_by=by,
    )


async def _list(c: Console, email: str) -> dict[str, dict]:
    data = await (await c.client.get("/api/connectors", headers=c.headers(email))).json()
    return {row["id"]: row for row in data["connectors"]}


async def test_a_member_sees_only_their_own_sign_ins_and_no_configuration(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _connectors(c)
        await c.tokens.put(_token("mail", c.world.alice.id, "Alice"))
        await c.tokens.put(_token("homey", None, "Alice"))
        rows = await _list(c, BOB)
        assert set(rows) == {"mail", "homey"}  # nothing to sign in to: not listed
        mail = rows["mail"]
        assert mail["config"] is None and mail["tools"] == [] and mail["used_by"] == []
        assert mail["sign_in"]["mode"] == "per_user"
        assert mail["sign_in"]["mine"]["signed_in"] is False  # Alice's is not Bob's
        assert mail["sign_in"]["shared"] is None and mail["sign_in"]["users"] is None
        homey = rows["homey"]["sign_in"]
        assert homey["mine"] is None and homey["shared"]["by"] == "Alice"
        assert "secret-access" not in str(rows)
        admin = await _list(c, ALICE)
        assert admin["mail"]["sign_in"]["users"] == 1 and admin["mail"]["config"] is not None
        assert admin["mail"]["sign_in"]["mine"]["signed_in"] is True
        assert admin["mail"]["sign_in_mode"] == "per_user"
        assert admin["local"]["sign_in"] is None and admin["local"]["sign_in_mode"] == "shared"
        assert "secret-access" not in str(admin)


async def test_a_member_signs_in_their_own_account_but_never_the_shared_one(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _connectors(c)
        bob = c.headers(BOB, write=True)
        r = await c.client.post("/api/connectors/mail/sign-in", headers=bob)
        assert r.status == 200
        query = parse_qs(urlsplit((await r.json())["url"]).query)
        assert query["client_id"] == ["cid"]
        shared = "/api/connectors/mail/sign-in?account=shared"
        assert (await c.client.post(shared, headers=bob)).status == 403
        assert (await c.client.post("/api/connectors/homey/sign-in", headers=bob)).status == 403
        mine = "/api/connectors/homey/sign-in?account=mine"
        assert (await c.client.post(mine, headers=bob)).status == 400
        alice = c.headers(ALICE, write=True)
        assert (await c.client.post(shared, headers=alice)).status == 200
        assert (await c.client.post("/api/connectors/nope/sign-in", headers=bob)).status == 404


async def test_signing_out_removes_only_the_callers_own_account(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _connectors(c)
        await c.tokens.put(_token("mail", c.world.alice.id, "Alice"))
        await c.tokens.put(_token("mail", c.world.bob.id, "Bob"))
        await c.tokens.put(_token("mail", None, "Alice"))
        r = await c.client.delete("/api/connectors/mail/sign-in", headers=c.headers(BOB, True))
        assert r.status == 200
        assert c.tokens.of_user("mail", c.world.bob.id) is None
        assert c.tokens.of_user("mail", c.world.alice.id) is not None
        assert c.tokens.shared("mail") is not None


async def test_saving_a_connector_keeps_its_sign_in_mode_unless_given(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _connectors(c)
        h = c.headers(ALICE, write=True)
        config = {"type": "http", "url": "https://mcp.example.com/mcp", "oauth": OAUTH}
        r = await c.client.put(
            "/api/connectors/mail", json={"config": config, "enabled": False}, headers=h
        )
        assert r.status == 200
        mail = c.agent_world.connector_store.get("mail")
        assert mail is not None and mail.sign_in is SignInMode.PER_USER
        body = {"config": config, "sign_in": "shared", "shared_fallback": True}
        await c.client.put("/api/connectors/mail", json=body, headers=h)
        mail = c.agent_world.connector_store.get("mail")
        assert mail is not None and mail.sign_in is SignInMode.SHARED and mail.shared_fallback


async def test_a_literal_secret_saved_in_the_console_becomes_a_variable(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {
            "name": "svc",
            "config": {
                "type": "http",
                "url": "https://s",
                "headers": {"Authorization": "Bearer x"},
            },
        }
        r = await c.client.post("/api/connectors", json=body, headers=h)
        assert r.status == 201
        data = await r.json()
        assert data["moved_secrets"] == ["SVC_AUTHORIZATION"]
        assert data["config"]["headers"]["Authorization"] == "${SVC_AUTHORIZATION}"
        saved = c.agent_world.connector_store.get("svc")
        assert saved is not None and "Bearer x" not in str(saved.config)
