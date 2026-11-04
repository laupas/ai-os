import json

import pytest

from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.common.id_generator import IdGenerator
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.users.permission import Permission
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.data_access_approval_rule import DataAccessApprovalRule
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
