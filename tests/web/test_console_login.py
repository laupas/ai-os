import yaml

from aios.config.web_auth_config import WebAuthConfig
from aios.web.login.web_sessions import COOKIE
from tests.web.console import ALICE, BOB, Console

PICK = WebAuthConfig(mode="pick")
PASSWORD = WebAuthConfig(mode="password")
CODE = WebAuthConfig(mode="code")
W = {"X-Aios": "1"}


async def _me(c: Console) -> int:
    return (await c.client.get("/api/conversations")).status


async def _you(c: Console) -> str:
    """Who the session is, as the login settings (administrators only) say."""
    return (await (await c.client.get("/api/settings/web-auth")).json())["you"]


async def test_with_a_login_of_its_own_the_page_opens_before_signing_in(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        assert (await c.client.get("/")).status == 200
        assert (await c.client.get("/static/assets/index-abc123.js")).status == 200
        assert await _me(c) == 403


async def test_behind_a_proxy_the_login_routes_are_not_open(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await c.client.get("/api/login")).status == 403
        page = await c.client.get("/api/login", headers=c.headers(ALICE))
        assert (await page.json())["mode"] is None


async def test_pick_lists_the_console_users_and_signs_in_the_one_picked(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        page = await (await c.client.get("/api/login")).json()
        assert page["mode"] == "pick"
        assert [u["id"] for u in page["users"]] == ["alice", "bob"]
        assert (await c.client.post("/api/login", json={"user_id": "bob"})).status == 403  # CSRF
        assert (await c.client.post("/api/login", json={"user_id": "x"}, headers=W)).status == 401
        assert (await c.client.post("/api/login", json={"user_id": "bob"}, headers=W)).status == 200
        assert await _me(c) == 200
        assert (
            await c.client.post("/api/login", json={"user_id": "alice"}, headers=W)
        ).status == 200
        assert await _you(c) == ALICE
        await c.client.post("/api/logout", headers=W)
        assert await _me(c) == 403


async def test_a_made_up_session_cookie_is_refused_and_only_its_hash_is_stored(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        await c.client.post("/api/login", json={"user_id": "bob"}, headers=W)
        assert await _me(c) == 200
        token = next(m.value for m in c.client.session.cookie_jar if m.key == COOKIE)
        assert all(token not in s.model_dump_json() for s in c.web_sessions.all())
        c.client.session.cookie_jar.clear()
        c.client.session.cookie_jar.update_cookies({COOKIE: token[:-2] + "xx"})
        assert await _me(c) == 403


async def test_a_session_from_another_mode_does_not_count(tmp_path) -> None:
    async with Console(tmp_path, auth=PASSWORD) as c:
        token = await c.sessions.issue("bob", "pick", "", 1)
        c.client.session.cookie_jar.update_cookies({COOKIE: token})
        assert await _me(c) == 403


async def test_password_signs_in_by_address_name_or_alias(tmp_path) -> None:
    async with Console(tmp_path, auth=PASSWORD) as c:
        login = {"username": "edi", "password": "correct horse"}
        assert (await c.client.post("/api/login", json=login, headers=W)).status == 401
        await c.passwords.set("bob", "correct horse", ALICE)
        for name in ("edi", "Bob", BOB.upper()):
            body = {"username": name, "password": "correct horse"}
            assert (await c.client.post("/api/login", json=body, headers=W)).status == 200
        assert await _me(c) == 200
        await c.passwords.set("alice", "alices password", ALICE)
        body = {"username": "alice", "password": "alices password"}
        await c.client.post("/api/login", json=body, headers=W)
        assert await _you(c) == ALICE
        wrong = {"username": "bob", "password": "wrong one"}
        assert (await c.client.post("/api/login", json=wrong, headers=W)).status == 401


async def test_a_new_password_ends_the_old_sessions(tmp_path) -> None:
    async with Console(tmp_path, auth=PASSWORD) as c:
        await c.passwords.set("bob", "first password", ALICE)
        body = {"username": "bob", "password": "first password"}
        await c.client.post("/api/login", json=body, headers=W)
        assert await _me(c) == 200
        await c.passwords.set("bob", "second password", ALICE)
        assert await _me(c) == 403


async def test_repeated_wrong_passwords_block_the_name_for_a_while(tmp_path) -> None:
    async with Console(tmp_path, auth=PASSWORD) as c:
        await c.passwords.set("bob", "correct horse", ALICE)
        for _ in range(5):
            wrong = {"username": "bob", "password": "nope nope"}
            await c.client.post("/api/login", json=wrong, headers=W)
        right = {"username": "bob", "password": "correct horse"}
        response = await c.client.post("/api/login", json=right, headers=W)
        assert response.status == 401 and "too many" in await response.text()


async def test_passwords_are_set_by_user_managers_and_by_each_user_for_themselves(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        a, b = c.headers(ALICE, write=True), c.headers(BOB, write=True)
        short = await c.client.put("/api/passwords/bob", json={"password": "short"}, headers=a)
        assert short.status == 400
        ok = await c.client.put("/api/passwords/bob", json={"password": "set by alice"}, headers=a)
        assert ok.status == 200
        listed = await (await c.client.get("/api/passwords", headers=a)).json()
        assert listed == {"mine": False, "users": ["bob"]}
        assert (await (await c.client.get("/api/passwords", headers=b)).json())["users"] is None
        other = await c.client.put("/api/passwords/alice", json={"password": "x" * 9}, headers=b)
        assert other.status == 403
        own = {"password": "bobs own one", "current": "wrong"}
        assert (await c.client.put("/api/me/password", json=own, headers=b)).status == 403
        own["current"] = "set by alice"
        assert (await c.client.put("/api/me/password", json=own, headers=b)).status == 200
        assert await c.passwords.verify("bob", "bobs own one")
        assert (await c.client.delete("/api/passwords/bob", headers=a)).status == 200
        assert not c.passwords.has("bob")


async def test_password_login_is_saved_only_once_you_have_a_password(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"auth": {"mode": "password"}}
        refused = await c.client.put("/api/settings/web-auth", json=body, headers=h)
        assert refused.status == 409 and "no password" in await refused.text()
        await c.passwords.set("alice", "alices password", ALICE)
        assert (await c.client.put("/api/settings/web-auth", json=body, headers=h)).status == 200
        assert yaml.safe_load(c.config_file.read_text())["web"]["auth"] == {"mode": "password"}
        pick = {"auth": {"mode": "pick"}}
        assert (await c.client.put("/api/settings/web-auth", json=pick, headers=h)).status == 200


def _code(c: Console) -> str:
    return c.signal.sent[-1][1].split(": ")[1].split()[0]


async def test_code_sends_a_one_time_code_to_the_users_chat(tmp_path) -> None:
    async with Console(tmp_path, auth=CODE) as c:
        ask = await c.client.post("/api/login", json={"username": "bob"}, headers=W)
        assert ask.status == 202 and (await ask.json())["pending"]
        account, text, _ = c.signal.sent[-1]
        assert account.address == "+41000000002" and "sign-in code" in text
        code = _code(c)
        wrong = {"username": "bob", "code": "000000" if code != "000000" else "111111"}
        assert (await c.client.post("/api/login", json=wrong, headers=W)).status == 401
        right = {"username": "bob", "code": code}
        assert (await c.client.post("/api/login", json=right, headers=W)).status == 200
        assert await _me(c) == 200
        again = await c.client.post("/api/login", json=right, headers=W)
        assert again.status == 401  # used once


async def test_code_answers_the_same_for_an_unknown_name_and_does_not_flood(tmp_path) -> None:
    async with Console(tmp_path, auth=CODE) as c:
        unknown = await c.client.post("/api/login", json={"username": "mallory"}, headers=W)
        assert unknown.status == 202 and c.signal.sent == []
        for _ in range(3):
            await c.client.post("/api/login", json={"username": "bob"}, headers=W)
        assert len(c.signal.sent) == 1


async def test_code_login_is_saved_only_when_you_can_be_reached(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"auth": {"mode": "code"}}
        assert (await c.client.put("/api/settings/web-auth", json=body, headers=h)).status == 200
        alice = c.world.users.get("alice")
        await c.world.users.put(
            alice.model_copy(
                update={"accounts": [a for a in alice.accounts if a.channel != "signal"]}
            )
        )
        refused = await c.client.put("/api/settings/web-auth", json=body, headers=h)
        assert refused.status == 409 and "cannot send you a code" in await refused.text()
