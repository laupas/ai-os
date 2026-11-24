from aiohttp.test_utils import make_mocked_request

from aios.config.rate_limit_config import RateLimitConfig
from aios.config.web_auth_config import WebAuthConfig
from aios.web.client_address import ClientAddress
from aios.web.rate.rate_buckets import RateBuckets
from tests.web.console import ALICE, BOB, Console

W = {"X-Aios": "1"}


def test_a_bucket_lets_a_burst_through_then_refills_over_the_minute() -> None:
    now = [0.0]
    buckets = RateBuckets(lambda: now[0])
    assert all(buckets.take("k", 3) == 0 for _ in range(3))
    assert buckets.take("k", 3) > 0
    now[0] += 20  # a third of a minute: one more
    assert buckets.take("k", 3) == 0
    assert buckets.take("other", 3) == 0  # keys are counted apart


def _request(remote: str, **headers: str):  # type: ignore[no-untyped-def]
    request = make_mocked_request("GET", "/", headers=headers)
    return request.clone(remote=remote)


def test_the_client_address_comes_from_the_proxy_only() -> None:
    address = ClientAddress(["172.16.0.0/12"])
    via_proxy = _request("172.19.0.8", **{"CF-Connecting-IP": "203.0.113.7"})
    assert address.of(via_proxy) == "203.0.113.7"
    forwarded = _request("172.19.0.8", **{"X-Forwarded-For": "198.51.100.1, 172.19.0.2"})
    assert address.of(forwarded) == "198.51.100.1"
    direct = _request("203.0.113.9", **{"CF-Connecting-IP": "1.2.3.4"})
    assert address.of(direct) == "203.0.113.9"  # a header from outside proves nothing


async def test_the_login_routes_are_limited_per_address(tmp_path) -> None:
    limits = RateLimitConfig(login_per_minute=3)
    async with Console(tmp_path, auth=WebAuthConfig(mode="pick"), rate_limits=limits) as c:
        answers = [(await c.client.get("/api/login")).status for _ in range(4)]
        assert answers == [200, 200, 200, 429]
        refused = await c.client.get("/api/login")
        assert int(refused.headers["Retry-After"]) >= 1
        c.now += 60
        assert (await c.client.get("/api/login")).status == 200


async def test_wrong_webhook_tokens_block_the_address(tmp_path) -> None:
    limits = RateLimitConfig(hook_failures=3, hook_block_minutes=15)
    async with Console(tmp_path, rate_limits=limits) as c:
        for _ in range(3):
            assert (await c.client.post("/hooks/triggers/x")).status == 404
        assert (await c.client.post("/hooks/triggers/x")).status == 429
        c.now += 16 * 60
        assert (await c.client.post("/hooks/triggers/x")).status == 404


async def test_messages_are_limited_per_user_apart_from_reads(tmp_path) -> None:
    limits = RateLimitConfig(messages_per_minute=2, reads_per_minute=100)
    async with Console(tmp_path, rate_limits=limits) as c:
        h = c.headers(BOB, write=True)
        started = [
            (await c.client.post("/api/conversations", json={"text": "hi"}, headers=h)).status
            for _ in range(3)
        ]
        assert started == [201, 201, 429]
        assert (await c.client.get("/api/conversations", headers=c.headers(BOB))).status == 200
        alice = await c.client.post(
            "/api/conversations", json={"text": "hi"}, headers=c.headers(ALICE, write=True)
        )
        assert alice.status == 201  # her own count


async def test_limits_can_be_switched_off(tmp_path) -> None:
    limits = RateLimitConfig(enabled=False, login_per_minute=1)
    async with Console(tmp_path, auth=WebAuthConfig(mode="pick"), rate_limits=limits) as c:
        assert {(await c.client.get("/api/login")).status for _ in range(5)} == {200}


async def test_a_group_sets_its_members_message_limit(tmp_path) -> None:
    from aios.entities.users.group import Group

    limits = RateLimitConfig(messages_per_minute=1)
    async with Console(tmp_path, rate_limits=limits) as c:
        await c.world.groups.put(Group(id="heavy", name="Heavy", messages_per_minute=3))
        await c.world.groups.put(Group(id="light", name="Light", messages_per_minute=2))
        bob = c.world.users.get("bob")
        await c.world.users.put(bob.model_copy(update={"group_ids": ["member", "light", "heavy"]}))  # type: ignore[union-attr]
        h = c.headers(BOB, write=True)
        started = [
            (await c.client.post("/api/conversations", json={"text": "hi"}, headers=h)).status
            for _ in range(4)
        ]
        assert started == [201, 201, 201, 429]  # the most generous group: 3
        alice = c.headers(ALICE, write=True)
        mine = [
            (await c.client.post("/api/conversations", json={"text": "hi"}, headers=alice)).status
            for _ in range(2)
        ]
        assert mine == [201, 429]  # no group limit: the general one


async def test_the_limits_are_edited_as_their_own_section_and_apply_at_once(tmp_path) -> None:
    async with Console(tmp_path) as c:
        saved = await c.client.put(
            "/api/settings/sections/rate_limits",
            json={"value": {"messages_per_minute": 5}},
            headers=c.headers(ALICE, write=True),
        )
        assert saved.status == 200
        assert c.live_config.current().rate_limits.messages_per_minute == 5
        needed = await c.client.get("/api/restart-needed", headers=c.headers(ALICE))
        assert (await needed.json())["restart_needed"] is False
