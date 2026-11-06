import json

import pytest

from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.common.id_generator import IdGenerator
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.memories.memory import Memory
from aios.entities.users.permission import Permission
from aios.storage.agent_access import AgentAccess
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.collection_registry import CollectionRegistry
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.data_access_approval_rule import DataAccessApprovalRule
from aios.tools.data_delete_tool import DataDeleteTool
from aios.tools.data_get_tool import DataGetTool
from aios.tools.data_put_tool import DataPutTool
from aios.tools.data_query_tool import DataQueryTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError
from tests.fakes.world import World


def _call(world: World, tool: str, **tool_input: object) -> ToolCall:
    return ToolCall(
        tool_name=f"mcp__aios__{tool}",
        tool_input=tool_input,
        user=world.alice,
        conversation_id="c",
    )


def _context(world: World) -> ToolContext:
    return ToolContext(
        conversation_id="c",
        user=world.alice,
        binding=ChannelBinding(channel="fake", address="a", thread="t"),
    )


async def test_reads_are_allowed_where_access_allows_them() -> None:
    world = await World().setup()
    rule = DataAccessApprovalRule(world.registry)
    assert (
        rule.evaluate(_call(world, "data_query", collection="users")).verdict is PolicyVerdict.ALLOW
    )  # type: ignore[union-attr]
    assert (
        rule.evaluate(_call(world, "data_query", collection="roles")).verdict is PolicyVerdict.DENY
    )  # type: ignore[union-attr]


async def test_writes_ask_with_the_collections_approver_permission() -> None:
    world = await World().setup()
    rule = DataAccessApprovalRule(world.registry)
    decision = rule.evaluate(_call(world, "data_put", collection="users", document={"name": "X"}))
    assert decision is not None and decision.verdict is PolicyVerdict.ASK
    assert decision.approver_permission is Permission.APPROVE
    assert '"X"' in decision.question


async def test_writes_to_read_only_collections_are_denied() -> None:
    world = await World().setup()
    rule = DataAccessApprovalRule(world.registry)
    decision = rule.evaluate(_call(world, "data_delete", collection="conversations", id="x"))
    assert decision is not None and decision.verdict is PolicyVerdict.DENY


async def test_put_validates_and_assigns_an_id() -> None:
    world = await World().setup()
    tool = DataPutTool(CollectionAccessGuard(world.registry), IdGenerator())
    await tool.run({"collection": "users", "document": {"name": "Anna"}}, _context(world))
    assert world.users.find(lambda u: u.name == "Anna") is not None
    with pytest.raises(ToolError, match="does not fit"):
        await tool.run(
            {"collection": "users", "document": {"aliases": "not a list"}}, _context(world)
        )


async def test_query_filters_on_top_level_fields() -> None:
    world = await World().setup()
    tool = DataQueryTool(CollectionAccessGuard(world.registry))
    result = json.loads(
        await tool.run({"collection": "users", "where": {"name": "Bob"}}, _context(world))
    )
    assert [r["id"] for r in result] == ["bob"]


async def _with_memories(world: World) -> Collection[Memory]:
    memories: Collection[Memory] = Collection(
        CollectionDefinition(
            name="memories",
            entity=Memory,
            agent_access=AgentAccess.WRITE,
            agent_writes_need_approval=False,
            approver_permission=Permission.ADMINISTER,
            owner_field="user_id",
        ),
        world.store,
    )
    world.registry = CollectionRegistry([*world.registry.all(), memories])
    await memories.put(Memory(id="own", user_id="alice", text="Alice's"))
    await memories.put(Memory(id="other", user_id="bob", text="Bob's"))
    await memories.put(Memory(id="shared", text="everyone's"))
    return memories


async def test_owned_collections_show_only_own_and_shared_documents() -> None:
    world = await World().setup()
    await _with_memories(world)
    guard = CollectionAccessGuard(world.registry)
    rows = json.loads(await DataQueryTool(guard).run({"collection": "memories"}, _context(world)))
    assert sorted(r["id"] for r in rows) == ["own", "shared"]
    with pytest.raises(ToolError, match="No document"):
        await DataGetTool(guard).run({"collection": "memories", "id": "other"}, _context(world))
    with pytest.raises(ToolError, match="No document"):
        await DataDeleteTool(guard).run({"collection": "memories", "id": "other"}, _context(world))


async def test_put_saves_for_the_turn_user_unless_shared() -> None:
    world = await World().setup()
    memories = await _with_memories(world)
    tool = DataPutTool(CollectionAccessGuard(world.registry), IdGenerator())
    await tool.run(
        {"collection": "memories", "document": {"id": "n", "text": "x"}}, _context(world)
    )
    assert memories.get("n").user_id == "alice"  # type: ignore[union-attr]
    await tool.run(
        {"collection": "memories", "document": {"id": "s", "text": "x", "user_id": None}},
        _context(world),
    )
    assert memories.get("s").user_id is None  # type: ignore[union-attr]
    with pytest.raises(ToolError, match="current user or is shared"):
        await tool.run(
            {"collection": "memories", "document": {"text": "x", "user_id": "bob"}},
            _context(world),
        )
    with pytest.raises(ToolError, match="No document"):
        await tool.run(
            {"collection": "memories", "document": {"id": "other", "text": "mine now"}},
            _context(world),
        )
    assert memories.get("other").user_id == "bob"  # type: ignore[union-attr]


async def test_only_shared_writes_ask_an_administrator() -> None:
    world = await World().setup()
    await _with_memories(world)
    rule = DataAccessApprovalRule(world.registry)

    def verdict(tool: str, **tool_input: object) -> PolicyDecision:
        decision = rule.evaluate(_call(world, tool, collection="memories", **tool_input))
        assert decision is not None
        return decision

    assert verdict("data_put", document={"text": "x"}).verdict is PolicyVerdict.ALLOW
    assert verdict("data_put", document={"id": "own", "text": "x"}).verdict is PolicyVerdict.ALLOW
    assert verdict("data_delete", id="own").verdict is PolicyVerdict.ALLOW
    shared = verdict("data_put", document={"text": "x", "user_id": None})
    assert shared.verdict is PolicyVerdict.ASK
    assert shared.approver_permission is Permission.ADMINISTER
    assert verdict("data_put", document={"id": "shared", "text": "x"}).verdict is PolicyVerdict.ASK
    assert verdict("data_delete", id="shared").verdict is PolicyVerdict.ASK


async def test_agents_see_only_conversations_the_turn_user_takes_part_in() -> None:
    world = await World().setup()
    conversations: Collection[Conversation] = Collection(
        CollectionDefinition(
            name="conversations",
            entity=Conversation,
            agent_access=AgentAccess.READ,
            owner_field="participants",
        ),
        world.store,
    )
    now = world.clock.now()
    for cid, participants in (("mine", ["alice"]), ("both", ["alice", "bob"]), ("his", ["bob"])):
        await conversations.put(
            Conversation(id=cid, participants=participants, created_at=now, updated_at=now)
        )
    guard = CollectionAccessGuard(CollectionRegistry([conversations]))
    rows = json.loads(
        await DataQueryTool(guard).run({"collection": "conversations"}, _context(world))
    )
    assert sorted(r["id"] for r in rows) == ["both", "mine"]
