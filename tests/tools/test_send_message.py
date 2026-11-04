import pytest

from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.message_role import MessageRole
from aios.messaging.sender_directory import SenderDirectory
from aios.tools.send_message_approval_rule import SendMessageApprovalRule
from aios.tools.send_message_tool import SendMessageTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError
from tests.fakes.fake_sender import FakeSender
from tests.fakes.world import World

TOOL = SendMessageApprovalRule.TOOL


def _call(world: World, recipient: str, via: str = "signal") -> ToolCall:
    return ToolCall(
        tool_name=TOOL,
        tool_input={"recipient": recipient, "via": via, "text": "late"},
        user=world.alice,
        conversation_id="c1",
    )


async def test_rule_asks_for_an_untrusted_recipient() -> None:
    world = await World().setup()
    rule = SendMessageApprovalRule(world.users, world.authorizer)
    decision = rule.evaluate(_call(world, "edi"))
    assert decision is not None and decision.verdict is PolicyVerdict.ASK
    assert "+41000000002" in decision.question


async def test_rule_allows_a_trusted_recipient() -> None:
    world = await World().setup()
    await world.users.put(world.bob.model_copy(update={"role_ids": ["trusted_contact"]}))
    rule = SendMessageApprovalRule(world.users, world.authorizer)
    decision = rule.evaluate(_call(world, "Bob"))
    assert decision is not None and decision.verdict is PolicyVerdict.ALLOW


async def test_rule_denies_unknown_recipient_or_missing_account() -> None:
    world = await World().setup()
    rule = SendMessageApprovalRule(world.users, world.authorizer)
    assert rule.evaluate(_call(world, "Nobody")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]
    assert rule.evaluate(_call(world, "Bob", "mail")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]


async def test_rule_ignores_other_tools() -> None:
    world = await World().setup()
    rule = SendMessageApprovalRule(world.users, world.authorizer)
    call = _call(world, "Bob").model_copy(update={"tool_name": "mcp__aios__data_query"})
    assert rule.evaluate(call) is None


def _tool(world: World, sender: FakeSender) -> SendMessageTool:
    senders = SenderDirectory({"signal": lambda: sender}, ["signal"])
    return SendMessageTool(world.users, senders, world.recorder)


def _context(world: World) -> ToolContext:
    return ToolContext(
        conversation_id="c1",
        user=world.alice,
        binding=ChannelBinding(channel="fake", address="room", thread="t"),
    )


async def test_tool_sends_to_the_users_account_and_records_it() -> None:
    world = await World().setup()
    sender = FakeSender()
    result = await _tool(world, sender).run(
        {"recipient": "Edi", "via": "signal", "text": "late"}, _context(world)
    )
    assert result == "Sent to Bob via signal."
    assert sender.sent[0][0].address == "+41000000002"
    [record] = await world.recorder.history("c1")
    assert record.role is MessageRole.TOOL and "sent" in record.text


async def test_tool_reports_a_failed_delivery() -> None:
    world = await World().setup()
    with pytest.raises(ToolError, match="boom"):
        await _tool(world, FakeSender(ok=False)).run(
            {"recipient": "Bob", "via": "signal", "text": "x"}, _context(world)
        )
    [record] = await world.recorder.history("c1")
    assert "FAILED" in record.text
