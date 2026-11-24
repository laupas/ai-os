import asyncio

import pytest
from pydantic import ValidationError

from aios.config.web_auth_config import WebAuthConfig
from aios.entities.users.permission import Permission
from tests.web.console import ALICE, Console

NEW = "carol@example.org"


def _carols(c: Console) -> list:
    return [u for u in c.world.users.all() if u.has_account("web", NEW)]


async def test_an_address_the_proxy_vouches_for_becomes_a_member(tmp_path) -> None:
    async with Console(tmp_path, new_users=("member", ["example.org"])) as c:
        assert (await c.client.get("/api/conversations", headers=c.headers(NEW))).status == 200
        [carol] = _carols(c)
        assert carol.group_ids == ["member"] and carol.name == "carol"
        assert (await c.client.get("/api/conversations", headers=c.headers(NEW))).status == 200
        assert len(_carols(c)) == 1


async def test_a_first_visit_of_many_requests_at_once_makes_one_user(tmp_path) -> None:
    async with Console(tmp_path, new_users=("member", ["example.org"])) as c:
        answers = await asyncio.gather(
            *(c.client.get("/api/conversations", headers=c.headers(NEW)) for _ in range(5))
        )
        assert {a.status for a in answers} == {200}
        assert len(_carols(c)) == 1


async def test_nobody_is_made_outside_the_domains_or_without_create_users(tmp_path) -> None:
    async with Console(tmp_path, new_users=("member", ["example.org"])) as c:
        stranger = c.headers("mallory@elsewhere.com")
        assert (await c.client.get("/api/conversations", headers=stranger)).status == 403
    (tmp_path / "off").mkdir()
    async with Console(tmp_path / "off") as c:
        assert (await c.client.get("/api/conversations", headers=c.headers(NEW))).status == 403
        assert _carols(c) == []


async def test_a_group_that_administers_is_never_given(tmp_path) -> None:
    async with Console(tmp_path, new_users=("owner", ["example.org"])) as c:
        assert (await c.client.get("/api/conversations", headers=c.headers(NEW))).status == 403
        assert _carols(c) == []


async def test_a_group_that_manages_connectors_is_never_given(tmp_path) -> None:
    # A connector runs programs and reads secrets: as good as administering.
    async with Console(tmp_path, new_users=("member", ["example.org"])) as c:
        await c.grant("member", Permission.MANAGE_CONNECTORS)
        assert (await c.client.get("/api/conversations", headers=c.headers(NEW))).status == 403
        assert _carols(c) == []


async def test_settings_refuse_a_default_group_that_administers(tmp_path) -> None:
    async with Console(tmp_path) as c:
        auth = {
            "mode": "header",
            "header": "X-Test-Email",
            "trusted_proxies": ["127.0.0.1"],
            "create_users": True,
            "domains": ["example.org"],
            "default_group": "owner",
        }
        tried = await c.client.post(
            "/api/settings/web-auth/check",
            json={"auth": auth},
            headers=c.headers(ALICE, write=True),
        )
        result = await tried.json()
        assert result["ok"] is False and "administers" in result["detail"]


def test_create_users_is_for_a_proxy_and_needs_domains() -> None:
    with pytest.raises(ValidationError, match="needs domains"):
        WebAuthConfig(mode="cloudflare", team_domain="t", audience="a", create_users=True)
    with pytest.raises(ValidationError, match="for a login proxy"):
        WebAuthConfig(mode="password", create_users=True, domains=["example.org"])
    auth = WebAuthConfig(
        mode="cloudflare",
        team_domain="t",
        audience="a",
        create_users=True,
        domains=["@Example.org"],
    )
    assert auth.domains == ["example.org"]
