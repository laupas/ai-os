from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from aios.audit.audit_feed import AuditFeed
from aios.audit.audit_policy import AuditPolicy
from aios.audit.audit_trail import AuditTrail
from aios.audit.audited_document_store import AuditedDocumentStore
from aios.audit.config_history import ConfigHistory
from aios.config_repo.change_author import ChangeAuthor
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.audit.audit_action import AuditAction
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_append_log import InMemoryAppendLog
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.web.audit_middleware import AuditMiddleware
from tests.config_repo.repo_world import RepoWorld
from tests.fakes.fake_clock import FakeClock

ALICE = ChangeAuthor(name="Alice", email="alice@example.com")


def audited() -> tuple[AuditTrail, AuditedDocumentStore]:
    trail = AuditTrail(InMemoryAppendLog(), FakeClock())
    store = AuditedDocumentStore(
        InMemoryDocumentStore(),
        trail,
        {
            "users": AuditPolicy(show_values=True),
            "connector-tokens": AuditPolicy(
                ignored_fields=frozenset({"access_token", "expires_at"})
            ),
        },
    )
    return trail, store


async def test_a_change_records_who_what_and_old_and_new_values() -> None:
    trail, store = audited()
    users: Collection[User] = Collection(CollectionDefinition(name="users", entity=User), store)
    CurrentAuthor.set(ALICE)
    await users.put(User(id="u1", name="Bob"))
    await users.put(User(id="u1", name="Bob", role_ids=["member"]))
    await users.put(User(id="u1", name="Bob", role_ids=["member"]))  # no change
    await users.delete("u1")
    created, changed, deleted = reversed(await trail.entries())
    assert (created.action, created.actor, created.item) == (AuditAction.CREATED, "Alice", "u1")
    assert changed.fields == ["role_ids"]
    assert changed.detail == 'role_ids: [] → ["member"]'
    assert deleted.action == AuditAction.DELETED


async def test_secret_values_are_never_recorded_and_renewals_are_not_changes() -> None:
    trail, store = audited()
    tokens: Collection[ConnectorToken] = Collection(
        CollectionDefinition(name="connector-tokens", entity=ConnectorToken), store
    )
    token = ConnectorToken(
        id="gmail.shared", connector="gmail", access_token="s3cret",
        token_endpoint="https://x/token", client_id="c",
    )  # fmt: skip
    await tokens.put(token)
    await tokens.put(token.model_copy(update={"access_token": "renewed"}))
    await tokens.put(token.model_copy(update={"client_id": "other"}))
    entries = await trail.entries()
    assert [e.action for e in entries] == [AuditAction.CHANGED, AuditAction.CREATED]
    assert entries[0].fields == ["client_id"] and entries[0].detail is None
    assert "s3cret" not in repr(entries) and "renewed" not in repr(entries)


async def test_other_collections_pass_through_unrecorded() -> None:
    trail, store = audited()
    await store.put("conversations", "c1", {"id": "c1"})
    await store.delete("conversations", "c1")
    assert await trail.entries() == []


async def test_the_feed_merges_the_trail_with_the_configuration_history(tmp_path) -> None:
    world = RepoWorld(tmp_path)
    world.repo.init()
    trail = AuditTrail(InMemoryAppendLog(), FakeClock())  # clock is in 2026-10
    CurrentAuthor.set(ALICE)
    await world.roles.put(Role(id="family", name="Family", permissions={Permission.CHAT}))
    await trail.record("users", "u1", AuditAction.CREATED)
    entries = await AuditFeed(trail, ConfigHistory(world.repo)).entries(50)
    from_git = next(e for e in entries if e.commit)
    assert (from_git.area, from_git.item, from_git.action) == ("roles", "family", "created")
    assert from_git.actor == "Alice"
    assert {e.area for e in entries} == {"roles", "users"}
    assert [
        e.area for e in await AuditFeed(trail, ConfigHistory(world.repo)).entries(50, "users")
    ] == ["users"]


def test_paths_name_their_area_and_item() -> None:
    assert ConfigHistory.place("agents/mail.md") == ("agents", "mail")
    assert ConfigHistory.place("skills/style/SKILL.md") == ("skills", "style")
    assert ConfigHistory.place("aios.yaml") == ("aios.yaml", "aios.yaml")


async def test_console_actions_are_recorded_only_when_they_succeed() -> None:
    trail = AuditTrail(InMemoryAppendLog(), FakeClock())

    async def ok(request: web.Request) -> web.Response:
        await request.json()
        return web.json_response({"ok": True})

    async def refused(request: web.Request) -> web.Response:
        raise web.HTTPBadRequest(text="no")

    app = web.Application(middlewares=[AuditMiddleware(trail).middleware])
    app.router.add_post("/api/git/switch", ok)
    app.router.add_post("/api/git/merge", refused)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/git/switch", json={"branch": "dev"})
        await client.post("/api/git/merge", json={"source": "dev", "into": "main"})
    (entry,) = await trail.entries()
    assert (entry.area, entry.item, entry.detail) == ("git", "switch branch", "branch: dev")


async def test_a_commit_in_the_feed_shows_its_diff(tmp_path) -> None:
    world = RepoWorld(tmp_path)
    world.repo.init()
    await world.roles.put(Role(id="family", name="Family", permissions={Permission.CHAT}))
    feed = AuditFeed(AuditTrail(InMemoryAppendLog(), FakeClock()), ConfigHistory(world.repo))
    (entry,) = await feed.entries(10)
    assert "+name: Family" in (await feed.diff(entry.commit or ""))  # type: ignore[operator]
