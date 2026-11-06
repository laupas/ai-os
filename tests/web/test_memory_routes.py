from tests.web.console import ALICE, BOB, Console


async def _create(c: Console, **body: object):  # type: ignore[no-untyped-def]
    return await c.client.post(
        "/api/memories", json={"text": "x", **body}, headers=c.headers(ALICE, write=True)
    )


async def test_a_memory_is_shared_unless_given_an_owner(tmp_path) -> None:
    async with Console(tmp_path) as c:
        shared = await (await _create(c)).json()
        own = await (await _create(c, user_id="bob")).json()
        assert c.memories.get(shared["id"]).user_id is None  # type: ignore[union-attr]
        assert c.memories.get(own["id"]).user_id == "bob"  # type: ignore[union-attr]
        assert (await _create(c, user_id="nobody")).status == 400

        listed = await (await c.client.get("/api/memories", headers=c.headers(ALICE))).json()
        assert {"id": "bob", "name": "Bob"} in listed["users"]


async def test_a_memory_can_be_moved_between_owners(tmp_path) -> None:
    async with Console(tmp_path) as c:
        memory_id = (await (await _create(c, user_id="alice")).json())["id"]
        response = await c.client.put(
            f"/api/memories/{memory_id}",
            json={"text": "x", "user_id": None},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        assert c.memories.get(memory_id).user_id is None  # type: ignore[union-attr]


async def test_only_administrators_see_memories(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await c.client.get("/api/memories", headers=c.headers(BOB))).status == 403
