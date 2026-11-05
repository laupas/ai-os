import asyncio
from datetime import UTC, datetime, timedelta

from aios.conversations.conversation_event import ConversationEvent
from aios.engine.text_delta import TextDelta
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.message_role import MessageRole
from tests.fakes.fake_engine import FakeEngine
from tests.web.console import ALICE, BOB, Console


async def test_a_request_without_an_identity_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.get("/api/conversations", headers=c.headers(None))
        assert response.status == 403


async def test_an_address_no_user_has_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.get("/api/conversations", headers=c.headers("x@example.com"))
        assert response.status == 403


async def test_the_web_address_is_matched_without_regard_to_case(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.get("/api/conversations", headers=c.headers(ALICE.upper()))
        assert response.status == 200


async def test_a_change_without_the_csrf_header_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/conversations", json={"text": "hi"}, headers=c.headers(ALICE)
        )
        assert response.status == 403
        assert c.world.conversations.all() == []


async def test_logs_are_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        member = await c.client.get("/api/logs", headers=c.headers(BOB))
        owner = await c.client.get("/api/logs?hours=1", headers=c.headers(ALICE))
        assert member.status == 403
        assert owner.status == 200


async def _events_until_done(c: Console, conversation_id: str, gate: asyncio.Event) -> list:
    queue = c.hub.subscribe(conversation_id)
    gate.set()
    events = []
    while not events or events[-1].kind != "message" or events[-1].message.role != "assistant":
        events.append(await asyncio.wait_for(queue.get(), 2))
    return events


async def test_a_web_conversation_streams_the_reply_and_then_records_it(tmp_path) -> None:
    gate = asyncio.Event()

    async def wait_for_watcher(request: object) -> None:
        await gate.wait()

    engine = FakeEngine(
        reply="Hello there",
        behaviour=wait_for_watcher,
        deltas=[
            TextDelta(text="", restart=True),
            TextDelta(text="Hello "),
            TextDelta(text="there"),
        ],
    )
    async with Console(tmp_path, engine) as c:
        response = await c.client.post(
            "/api/conversations", json={"text": "hello"}, headers=c.headers(ALICE, write=True)
        )
        assert response.status == 201
        conversation_id = (await response.json())["id"]

        events = await _events_until_done(c, conversation_id, gate)

        assert [e.kind for e in events] == ["delta", "delta", "delta", "done", "message"]
        assert "".join(e.text for e in events if e.kind == "delta") == "Hello there"
        assert events[-1].message.text == "Hello there"
        read = await (
            await c.client.get(f"/api/conversations/{conversation_id}", headers=c.headers(ALICE))
        ).json()
        assert [m["text"] for m in read["messages"]] == ["hello", "Hello there"]
        assert read["writable"] is True


async def test_a_conversation_on_another_channel_can_be_watched(tmp_path) -> None:
    async with Console(tmp_path) as c:
        conversation = await c.world.resolver.resolve(
            ChannelBinding(channel="slack", address="C1", thread="1"), c.world.alice
        )
        queue = c.hub.subscribe(conversation.id)

        await c.recorder.record(conversation.id, MessageRole.ASSISTANT, "from slack", "slack")

        event = await asyncio.wait_for(queue.get(), 1)
        assert event.message.text == "from slack"


async def test_a_conversation_can_be_deleted_with_its_history(tmp_path) -> None:
    async with Console(tmp_path) as c:
        started = await c.client.post(
            "/api/conversations", json={"text": "hello"}, headers=c.headers(ALICE, write=True)
        )
        conversation_id = (await started.json())["id"]
        await asyncio.sleep(0.05)

        response = await c.client.delete(
            f"/api/conversations/{conversation_id}", headers=c.headers(ALICE, write=True)
        )

        assert response.status == 200
        assert c.world.conversations.get(conversation_id) is None
        assert await c.recorder.history(conversation_id) == []


async def test_a_member_cannot_delete_someone_elses_conversation(tmp_path) -> None:
    async with Console(tmp_path) as c:
        started = await c.client.post(
            "/api/conversations", json={"text": "hello"}, headers=c.headers(ALICE, write=True)
        )
        conversation_id = (await started.json())["id"]

        response = await c.client.delete(
            f"/api/conversations/{conversation_id}", headers=c.headers(BOB, write=True)
        )

        assert response.status == 404
        assert c.world.conversations.get(conversation_id) is not None


async def test_prune_deletes_only_conversations_quiet_for_long_enough(tmp_path) -> None:
    async with Console(tmp_path) as c:
        old = await c.world.resolver.resolve(
            ChannelBinding(channel="slack", address="C1", thread="old"), c.world.alice
        )
        await c.world.conversations.put(
            old.model_copy(update={"updated_at": datetime.now(UTC) - timedelta(days=40)})
        )
        fresh = await c.world.resolver.resolve(
            ChannelBinding(channel="slack", address="C1", thread="new"), c.world.alice
        )
        await c.world.conversations.put(fresh.model_copy(update={"updated_at": datetime.now(UTC)}))

        response = await c.client.post(
            "/api/conversations/prune", json={"days": 30}, headers=c.headers(ALICE, write=True)
        )

        assert (await response.json())["deleted"] == 1
        assert c.world.conversations.get(old.id) is None
        assert c.world.conversations.get(fresh.id) is not None


async def test_someone_elses_conversation_is_hidden_from_a_member(tmp_path) -> None:
    async with Console(tmp_path) as c:
        started = await c.client.post(
            "/api/conversations", json={"text": "hello"}, headers=c.headers(ALICE, write=True)
        )
        conversation_id = (await started.json())["id"]

        listed = await (await c.client.get("/api/conversations", headers=c.headers(BOB))).json()
        read = await c.client.get(f"/api/conversations/{conversation_id}", headers=c.headers(BOB))

        assert listed["conversations"] == []
        assert read.status == 404


async def test_a_member_cannot_write_into_someone_elses_conversation(tmp_path) -> None:
    async with Console(tmp_path) as c:
        started = await c.client.post(
            "/api/conversations", json={"text": "hello"}, headers=c.headers(ALICE, write=True)
        )
        conversation_id = (await started.json())["id"]

        response = await c.client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"text": "me too"},
            headers=c.headers(BOB, write=True),
        )

        assert response.status == 404


async def test_writing_into_a_slack_conversation_reaches_slack_too(tmp_path) -> None:
    async with Console(tmp_path) as c:
        slack_thread = ChannelBinding(channel="slack", address="C1", thread="1")
        conversation = await c.world.resolver.resolve(slack_thread, c.world.alice)

        response = await c.client.post(
            f"/api/conversations/{conversation.id}/messages",
            json={"text": "wohnort?"},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 202
        for _ in range(50):
            if len(c.slack.sent) >= 2:
                break
            await asyncio.sleep(0.01)

        assert c.slack.sent == [(slack_thread, "*Alice (web):* wohnort?"), (slack_thread, "ok")]
        stored = c.world.conversations.get(conversation.id)
        assert stored is not None and {b.channel for b in stored.bindings} == {"slack", "web"}


async def test_an_invalid_config_is_refused_and_not_written(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/config",
            json={"text": "channels: nope-not-a-list: ["},
            headers=c.headers(ALICE, write=True),
        )
        wrong_type = await c.client.put(
            "/api/settings/config",
            json={"text": "scheduler: {tick_seconds: soon}"},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 400
        assert wrong_type.status == 400
        assert c.config_file.read_text() == "channels: [web]\n"


async def test_a_valid_config_is_written(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/config",
            json={"text": "channels: [web, slack]\n"},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        assert c.config_file.read_text() == "channels: [web, slack]\n"


async def test_settings_are_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/config",
            json={"text": "channels: [web]\n"},
            headers=c.headers(BOB, write=True),
        )
        assert response.status == 403


async def test_an_administrator_cannot_delete_themselves(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.delete(
            "/api/settings/users/alice", headers=c.headers(ALICE, write=True)
        )
        assert response.status == 409
        assert c.world.users.get("alice") is not None


async def test_restart_is_requested_after_answering(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post("/api/restart", headers=c.headers(ALICE, write=True))
        assert response.status == 202
        await asyncio.wait_for(c.restart.wait(), 2)


async def test_the_page_is_never_cached_and_its_hashed_assets_always_are(tmp_path) -> None:
    async with Console(tmp_path) as c:
        page = await c.client.get("/", headers=c.headers(ALICE))
        script = await c.client.get("/static/assets/index-abc123.js", headers=c.headers(ALICE))
        api = await c.client.get("/api/conversations", headers=c.headers(ALICE))

        assert "/static/assets/index-abc123.js" in await page.text()
        assert page.headers["Cache-Control"] == "no-cache"
        assert script.headers["Cache-Control"] == "public, max-age=31536000, immutable"
        assert api.headers["Cache-Control"] == "no-cache"


async def test_the_page_still_needs_a_signed_in_user(tmp_path) -> None:
    async with Console(tmp_path) as c:
        page = await c.client.get("/", headers=c.headers(None))
        script = await c.client.get("/static/assets/index-abc123.js", headers=c.headers(None))
        assert page.status == 403 and script.status == 403


async def test_a_tab_that_comes_back_mid_turn_gets_the_steps_so_far(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.hub.notify(ConversationEvent(conversation_id="x", kind="progress", text="config_put"))
        c.hub.notify(ConversationEvent(conversation_id="x", kind="delta", text="Saving"))
        queue = c.hub.subscribe("x")
        assert [queue.get_nowait().text for _ in range(2)] == ["config_put", "Saving"]

        c.hub.notify(ConversationEvent(conversation_id="x", kind="done"))
        assert c.hub.subscribe("x").empty()


async def test_reading_a_conversation_lists_its_waiting_approvals(tmp_path) -> None:
    async with Console(tmp_path) as c:
        binding = ChannelBinding(channel="web", address=ALICE, thread="t")
        conversation = await c.world.resolver.resolve(binding, c.world.alice)
        asking = asyncio.create_task(
            c.world.approval_service.request(conversation.id, binding, "Save it?", ["Yes", "No"])
        )
        await asyncio.sleep(0.05)

        read = await c.client.get(f"/api/conversations/{conversation.id}", headers=c.headers(ALICE))
        approvals = (await read.json())["approvals"]
        assert [a["question"] for a in approvals] == ["Save it?"]

        await c.world.approval_service.answer(approvals[0]["id"], "Yes", c.world.alice.accounts[0])
        assert await asking == "Yes"
        read = await c.client.get(f"/api/conversations/{conversation.id}", headers=c.headers(ALICE))
        assert (await read.json())["approvals"] == []
