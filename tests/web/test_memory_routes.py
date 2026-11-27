from aios.entities.users.permission import Permission
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


async def test_a_member_sees_their_own_and_the_shared_memories_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _create(c, text="shared")
        await _create(c, text="alice's", user_id="alice")
        await _create(c, text="bob's", user_id="bob")
        listed = await (await c.client.get("/api/memories", headers=c.headers(BOB))).json()
        assert sorted(m["text"] for m in listed["memories"]) == ["bob's", "shared"]
        assert {m["text"]: m["editable"] for m in listed["memories"]} == {
            "bob's": True,
            "shared": False,
        }
        assert listed["users"] == [{"id": "bob", "name": "Bob"}]


async def test_a_member_writes_only_their_own_memories(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(BOB, write=True)
        own = await c.client.post("/api/memories", json={"text": "x", "user_id": "bob"}, headers=h)
        assert own.status == 201
        theirs = await c.client.post(
            "/api/memories", json={"text": "x", "user_id": "alice"}, headers=h
        )
        assert theirs.status == 403
        shared = await c.client.post("/api/memories", json={"text": "x"}, headers=h)
        assert shared.status == 403
        alices = (await (await _create(c, user_id="alice")).json())["id"]
        assert (await c.client.delete(f"/api/memories/{alices}", headers=h)).status == 404
        # Nor may they hand their own memory to someone else.
        moved = await c.client.put(
            f"/api/memories/{(await own.json())['id']}",
            json={"text": "x", "user_id": "alice"},
            headers=h,
        )
        assert moved.status == 403


async def test_shared_memories_need_their_own_right(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.grant("member", Permission.MANAGE_SHARED_MEMORIES)
        h = c.headers(BOB, write=True)
        shared = await c.client.post("/api/memories", json={"text": "x"}, headers=h)
        assert shared.status == 201
        theirs = await c.client.post(
            "/api/memories", json={"text": "x", "user_id": "alice"}, headers=h
        )
        assert theirs.status == 403


async def test_a_console_write_records_its_source_and_keeps_the_creation_date(tmp_path) -> None:
    async with Console(tmp_path) as c:
        made = await (await _create(c, user_id="alice")).json()
        assert made["source"] == {"channel": "console", "conversation_id": None, "user_id": "alice"}
        assert made["updated_at"] is None
        changed = await (
            await c.client.put(
                f"/api/memories/{made['id']}",
                json={"text": "y", "user_id": "alice"},
                headers=c.headers(ALICE, write=True),
            )
        ).json()
        assert changed["created_at"] == made["created_at"] and changed["updated_at"]


async def test_merging_keeps_the_first_and_deletes_the_others(tmp_path) -> None:
    async with Console(tmp_path) as c:
        a = (await (await _create(c, user_id="bob", text="a")).json())["id"]
        b = (await (await _create(c, user_id="bob", text="b")).json())["id"]
        merged = await c.client.post(
            "/api/memories/merge",
            json={
                "ids": [a, b],
                "kind": "person",
                "subject": "Ann",
                "text": "a b",
                "user_id": "bob",
            },
            headers=c.headers(BOB, write=True),
        )
        assert merged.status == 200
        kept = c.memories.get(a)
        assert kept is not None and kept.text == "a b" and kept.subject == "Ann"
        assert c.memories.get(b) is None


async def test_a_merge_touching_a_memory_one_may_not_write_changes_nothing(tmp_path) -> None:
    async with Console(tmp_path) as c:
        own = (await (await _create(c, user_id="bob", text="own")).json())["id"]
        shared = (await (await _create(c, text="shared")).json())["id"]
        merged = await c.client.post(
            "/api/memories/merge",
            json={"ids": [own, shared], "text": "both", "user_id": "bob"},
            headers=c.headers(BOB, write=True),
        )
        assert merged.status == 403
        assert c.memories.get(own).text == "own"  # type: ignore[union-attr]
        assert c.memories.get(shared) is not None


async def test_the_prompt_preview_is_ones_own_unless_an_administrator(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _create(c, user_id="bob", kind="preference", subject="Tone", text="brief")
        await _create(c, user_id="bob", kind="person", subject="Ann", text="a friend")
        own = await (await c.client.get("/api/memories/prompt", headers=c.headers(BOB))).json()
        assert "- Tone: brief" in own["text"] and "- People: Ann" in own["text"]
        assert "a friend" not in own["text"]
        other = await c.client.get("/api/memories/prompt?user_id=alice", headers=c.headers(BOB))
        assert other.status == 403
        seen = await c.client.get("/api/memories/prompt?user_id=bob", headers=c.headers(ALICE))
        assert seen.status == 200
