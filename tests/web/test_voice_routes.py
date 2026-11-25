import asyncio

from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.permission import Permission
from tests.fakes.fake_engine import FakeEngine
from tests.fakes.fake_transcriber import FakeTranscriber
from tests.web.console import ALICE, BOB, Console


async def test_voice_is_available_when_transcription_is(tmp_path) -> None:
    async with Console(tmp_path, transcriber=FakeTranscriber(available=False)) as c:
        response = await c.client.get("/api/voice", headers=c.headers(ALICE))
        assert await response.json() == {"available": False}


async def test_a_recording_comes_back_as_text(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/voice/transcriptions",
            data=b"opus",
            headers={**c.headers(ALICE, write=True), "Content-Type": "audio/webm;codecs=opus"},
        )
        assert response.status == 200
        assert await response.json() == {"text": "hello by voice"}
        assert c.transcriber.calls == [(b"opus", "speech.webm")]


async def test_voice_is_a_permission_of_its_own(tmp_path) -> None:
    # Bob may chat, but every recording costs a transcription.
    async with Console(tmp_path) as c:
        h = {**c.headers(BOB, write=True), "Content-Type": "audio/webm"}
        assert (await c.client.get("/api/voice", headers=c.headers(BOB))).status == 403
        refused = await c.client.post("/api/voice/transcriptions", data=b"opus", headers=h)
        assert refused.status == 403 and c.transcriber.calls == []
        await c.grant("member", Permission.VOICE)
        allowed = await c.client.post("/api/voice/transcriptions", data=b"opus", headers=h)
        assert allowed.status == 200


async def test_safari_recordings_keep_their_format(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.client.post(
            "/api/voice/transcriptions",
            data=b"aac",
            headers={**c.headers(ALICE, write=True), "Content-Type": "audio/mp4"},
        )
        assert c.transcriber.calls[0][1] == "speech.mp4"


async def test_a_transcription_needs_the_csrf_header(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/voice/transcriptions",
            data=b"opus",
            headers={**c.headers(ALICE), "Content-Type": "audio/webm"},
        )
        assert response.status == 403
        assert c.transcriber.calls == []


async def test_a_recording_may_be_larger_than_other_requests(tmp_path) -> None:
    audio = b"x" * (2 * 1024**2)  # twice the server-wide limit
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/voice/transcriptions",
            data=audio,
            headers={**c.headers(ALICE, write=True), "Content-Type": "audio/wav"},
        )
        assert response.status == 200
        assert c.transcriber.calls == [(audio, "speech.wav")]


async def test_a_recording_over_the_limit_is_refused(tmp_path) -> None:
    async with Console(tmp_path, max_audio_bytes=10) as c:
        response = await c.client.post(
            "/api/voice/transcriptions",
            data=b"x" * 11,
            headers={**c.headers(ALICE, write=True), "Content-Type": "audio/wav"},
        )
        assert response.status == 413
        assert c.transcriber.calls == []


async def test_what_is_not_audio_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/voice/transcriptions",
            data=b"{}",
            headers={**c.headers(ALICE, write=True), "Content-Type": "application/json"},
        )
        empty = await c.client.post(
            "/api/voice/transcriptions",
            data=b"",
            headers={**c.headers(ALICE, write=True), "Content-Type": "audio/webm"},
        )
        assert response.status == 415 and empty.status == 400
        assert c.transcriber.calls == []


async def test_without_transcription_a_recording_is_refused(tmp_path) -> None:
    async with Console(tmp_path, transcriber=FakeTranscriber(available=False)) as c:
        response = await c.client.post(
            "/api/voice/transcriptions",
            data=b"opus",
            headers={**c.headers(ALICE, write=True), "Content-Type": "audio/webm"},
        )
        assert response.status == 503


async def test_a_spoken_message_asks_for_a_reply_to_be_read_aloud(tmp_path) -> None:
    engine = FakeEngine()
    async with Console(tmp_path, engine) as c:
        started = await c.client.post(
            "/api/conversations",
            json={"text": "hello", "voice": True},
            headers=c.headers(ALICE, write=True),
        )
        conversation_id = (await started.json())["id"]
        await asyncio.sleep(0.05)
        await c.client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"text": "typed now"},
            headers=c.headers(ALICE, write=True),
        )
        await asyncio.sleep(0.05)
        assert [(r.text, r.voice) for r in engine.requests] == [
            ("hello", True),
            ("typed now", False),
        ]


async def _ask(c: Console, voice_answerable: bool) -> tuple[asyncio.Task, str]:
    binding = ChannelBinding(channel="web", address=ALICE, thread="t")
    conversation = await c.world.resolver.resolve(binding, c.world.alice)
    asking = asyncio.create_task(
        c.world.approval_service.request(
            conversation.id,
            binding,
            "Carol?",
            ["Carol", "Dave"],
            voice_answerable=voice_answerable,
        )
    )
    await asyncio.sleep(0.05)
    return asking, c.world.approvals.all()[0].id


async def test_a_question_may_be_answered_by_voice(tmp_path) -> None:
    async with Console(tmp_path) as c:
        asking, approval_id = await _ask(c, voice_answerable=True)
        response = await c.client.post(
            f"/api/approvals/{approval_id}",
            json={"answer": "Carol", "voice": True},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        assert await asking == "Carol"


async def test_permission_for_a_tool_is_never_given_by_voice(tmp_path) -> None:
    async with Console(tmp_path) as c:
        asking, approval_id = await _ask(c, voice_answerable=False)
        spoken = await c.client.post(
            f"/api/approvals/{approval_id}",
            json={"answer": "Carol", "voice": True},
            headers=c.headers(ALICE, write=True),
        )
        assert spoken.status == 403 and not asking.done()
        tapped = await c.client.post(
            f"/api/approvals/{approval_id}",
            json={"answer": "Carol"},
            headers=c.headers(ALICE, write=True),
        )
        assert tapped.status == 200
        assert await asking == "Carol"
