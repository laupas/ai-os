from collections.abc import Awaitable, Callable

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from aios.conversations.artifact_store import ArtifactStore
from aios.entities.artifacts.artifact import Artifact
from aios.entities.artifacts.artifact_format import ArtifactFormat
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.web.routes.artifact_routes import ArtifactRoutes
from aios.web.web_auth import CALLER
from aios.web.web_caller import WebCaller
from tests.fakes.world import World

PAGE = "<!doctype html><h1>Report</h1><script>document.title='x'</script>"


def _caller(user: User, *permissions: Permission) -> WebCaller:
    return WebCaller(
        user=user,
        account=ChannelAccount(channel="web", address=f"{user.id}@example.com"),
        permissions={Permission.CHAT, *permissions},
    )


async def _client(callers: dict[str, WebCaller]) -> tuple[TestClient, ArtifactStore]:
    """A server with only the artifact routes; the `As` header picks the caller."""
    world = await World().setup()
    store = ArtifactStore(world.store)
    now = world.clock.now()
    await world.conversations.put(
        Conversation(id="c1", participants=["alice"], created_at=now, updated_at=now)
    )
    for artifact_id, format, content in [
        ("a1", ArtifactFormat.HTML, PAGE),
        ("a2", ArtifactFormat.MARKDOWN, "# Notes"),
    ]:
        await store.put(
            Artifact(
                id=artifact_id,
                conversation_id="c1",
                user_id="alice",
                title="Run report",
                format=format,
                content=content,
                created_at=now,
            )
        )

    @web.middleware
    async def identify(
        request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
    ) -> web.StreamResponse:
        request[CALLER] = callers[request.headers["As"]]
        return await handler(request)

    app = web.Application(middlewares=[identify])
    ArtifactRoutes(store, world.conversations).register(app)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client, store


async def test_a_participant_gets_the_page_sandboxed_in_its_own_origin() -> None:
    world = await World().setup()
    client, _ = await _client({"alice": _caller(world.alice)})
    try:
        response = await client.get("/api/artifacts/a1", headers={"As": "alice"})
        assert response.status == 200
        assert await response.text() == PAGE
        assert response.content_type == "text/html"
        csp = response.headers["Content-Security-Policy"]
        assert csp.startswith("sandbox allow-scripts") and "allow-same-origin" not in csp
        assert "connect-src 'none'" in csp and "frame-ancestors 'self'" in csp
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert "Content-Disposition" not in response.headers
    finally:
        await client.close()


async def test_markdown_is_plain_text_and_a_download_is_an_attachment() -> None:
    world = await World().setup()
    client, _ = await _client({"alice": _caller(world.alice)})
    try:
        response = await client.get("/api/artifacts/a2?download=1", headers={"As": "alice"})
        assert response.content_type == "text/plain"
        assert response.headers["Content-Disposition"] == 'attachment; filename="Run-report.md"'
    finally:
        await client.close()


async def test_others_do_not_see_it_administrators_do() -> None:
    world = await World().setup()
    client, _ = await _client(
        {"bob": _caller(world.bob), "admin": _caller(world.bob, Permission.ADMINISTER)}
    )
    try:
        assert (await client.get("/api/artifacts/a1", headers={"As": "bob"})).status == 404
        assert (await client.get("/api/artifacts/a1", headers={"As": "admin"})).status == 200
        assert (await client.get("/api/artifacts/nope", headers={"As": "admin"})).status == 404
    finally:
        await client.close()
