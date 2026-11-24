from datetime import timedelta

from aios.config.web_auth_config import WebAuthConfig
from aios.web.login.web_sessions import COOKIE
from tests.web.console import Console

PICK = WebAuthConfig(mode="pick")
W = {"X-Aios": "1"}


async def _me(c: Console, token: str | None = None) -> int:
    """Whether a browser holding `token` (or the current one) gets in."""
    if token is None:
        return (await c.client.get("/api/conversations")).status
    jar = c.client.session.cookie_jar
    saved = {m.key: m.value for m in jar}
    jar.clear()
    jar.update_cookies({COOKIE: token})
    status = (await c.client.get("/api/conversations")).status
    jar.clear()
    jar.update_cookies(saved)
    return status


async def _sign_in(c: Console, user_id: str) -> str:
    """Signs in as `user_id` in a fresh browser; returns its cookie."""
    c.client.session.cookie_jar.clear()
    await c.client.post("/api/login", json={"user_id": user_id}, headers=W)
    return next(m.value for m in c.client.session.cookie_jar if m.key == COOKIE)


async def test_signing_out_ends_the_session_on_the_server(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        token = await _sign_in(c, "bob")
        await c.client.post("/api/logout", headers=W)
        c.client.session.cookie_jar.clear()
        assert await _me(c, token) == 403  # a copied cookie is worth nothing now


async def test_a_user_sees_their_browsers_and_ends_one_or_all_others(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        phone = await _sign_in(c, "bob")
        laptop = await _sign_in(c, "bob")
        mine = await (await c.client.get("/api/sessions")).json()
        assert mine["own_login"] is True and len(mine["sessions"]) == 2
        [other] = [s for s in mine["sessions"] if not s["current"]]
        assert (await c.client.delete(f"/api/sessions/{other['id']}", headers=W)).status == 200
        assert await _me(c, phone) == 403 and await _me(c, laptop) == 200
        third = await _sign_in(c, "bob")
        c.client.session.cookie_jar.clear()
        c.client.session.cookie_jar.update_cookies({COOKIE: laptop})
        ended = await c.client.post("/api/sessions/end-all", headers=W)
        assert (await ended.json())["ended"] == 1
        assert await _me(c, third) == 403 and await _me(c, laptop) == 200


async def test_an_administrator_signs_someone_out_everywhere_others_cannot(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        bob = await _sign_in(c, "bob")
        assert (await c.client.get("/api/sessions?user=alice")).status == 403
        await _sign_in(c, "alice")
        theirs = await (await c.client.get("/api/sessions?user=bob")).json()
        assert len(theirs["sessions"]) == 1
        await c.client.post("/api/sessions/end-all?user=bob", headers=W)
        assert await _me(c, bob) == 403


async def test_deleting_a_user_ends_their_sessions(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        await _sign_in(c, "bob")
        await _sign_in(c, "alice")
        assert (await c.client.delete("/api/settings/users/bob", headers=W)).status == 200
        assert [s for s in c.web_sessions.all() if s.user_id == "bob"] == []


async def test_a_session_ends_after_the_idle_limit(tmp_path) -> None:
    async with Console(tmp_path, auth=WebAuthConfig(mode="pick", idle_minutes=30)) as c:
        token = await _sign_in(c, "bob")
        c.world.clock.advance(timedelta(minutes=20))
        assert await _me(c, token) == 200  # a request keeps it alive
        c.world.clock.advance(timedelta(minutes=20))
        assert await _me(c, token) == 200
        c.world.clock.advance(timedelta(minutes=31))
        assert await _me(c, token) == 403


async def test_a_session_ends_when_it_expires(tmp_path) -> None:
    async with Console(tmp_path, auth=PICK) as c:
        token = await _sign_in(c, "bob")
        c.world.clock.advance(timedelta(days=31))
        assert await _me(c, token) == 403
