import pytest

from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.message_role import MessageRole
from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.delivery_result import DeliveryResult
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.tools.send_webhook_approval_rule import SendWebhookApprovalRule
from aios.tools.send_webhook_tool import SendWebhookTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError
from tests.fakes.world import World

TOOL = SendWebhookApprovalRule.TOOL


class FakePoster(WebhookPoster):
    def __init__(self, enabled: bool = True, ok: bool = True) -> None:
        self._enabled = enabled
        self._ok = ok
        self.posted: list[tuple[str, dict]] = []

    async def post(self, destination, fields):  # type: ignore[no-untyped-def]
        self.posted.append((destination.id, fields))
        return DeliveryResult(ok=self._ok, detail="200 ok" if self._ok else "boom")


async def _destinations(world: World) -> Collection[WebhookDestination]:
    destinations: Collection[WebhookDestination] = Collection(
        CollectionDefinition(name="webhooks", entity=WebhookDestination), world.store
    )
    for name, approval in (("n8n", "ask"), ("lamp", "allow"), ("bank", "deny")):
        await destinations.put(
            WebhookDestination(
                id=name, description=f"The {name}.", url="https://x.test/", approval=approval
            )
        )
    await destinations.put(WebhookDestination(id="old", url="https://x.test/", enabled=False))
    return destinations


def _call(world: World, destination: str, fields: object = None) -> ToolCall:
    return ToolCall(
        tool_name=TOOL,
        tool_input={"destination": destination, "fields": fields or {"text": "hi"}},
        user=world.alice,
        conversation_id="c1",
    )


async def test_the_rule_follows_each_destinations_approval() -> None:
    world = await World().setup()
    rule = SendWebhookApprovalRule(await _destinations(world))
    asked = rule.evaluate(_call(world, "n8n"))
    assert asked is not None and asked.verdict is PolicyVerdict.ASK
    assert "n8n" in asked.question and '"hi"' in asked.question
    assert rule.evaluate(_call(world, "lamp")).verdict is PolicyVerdict.ALLOW  # type: ignore[union-attr]
    assert rule.evaluate(_call(world, "bank")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]


async def test_the_rule_refuses_unknown_destinations_and_unfit_fields() -> None:
    world = await World().setup()
    rule = SendWebhookApprovalRule(await _destinations(world))
    for call in (
        _call(world, "nowhere"),
        _call(world, "old"),
        _call(world, "lamp", {"txt": "typo"}),
    ):
        assert rule.evaluate(call).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]
    other = _call(world, "n8n").model_copy(update={"tool_name": "mcp__aios__data_query"})
    assert rule.evaluate(other) is None


def _context(world: World) -> ToolContext:
    return ToolContext(
        conversation_id="c1",
        user=world.alice,
        binding=ChannelBinding(channel="fake", address="room", thread="t"),
    )


async def test_the_tool_lists_the_usable_destinations() -> None:
    world = await World().setup()
    tool = SendWebhookTool(await _destinations(world), FakePoster(), world.recorder)
    assert tool.input_schema["properties"]["destination"]["enum"] == ["bank", "lamp", "n8n"]
    assert "The lamp." in tool.description and "old" not in tool.description
    off = SendWebhookTool(await _destinations(world), FakePoster(enabled=False), world.recorder)
    assert off.input_schema["properties"]["destination"]["enum"] == ["none"]


async def test_the_tool_posts_and_records_it() -> None:
    world = await World().setup()
    poster = FakePoster()
    tool = SendWebhookTool(await _destinations(world), poster, world.recorder)
    result = await tool.run({"destination": "lamp", "fields": {"text": "on"}}, _context(world))
    assert result == "Posted to lamp: 200 ok"
    assert poster.posted == [("lamp", {"text": "on"})]
    [record] = await world.recorder.history("c1")
    assert record.role is MessageRole.TOOL and "webhook lamp sent" in record.text


async def test_the_tool_reports_a_failure_and_refuses_when_off() -> None:
    world = await World().setup()
    destinations = await _destinations(world)
    with pytest.raises(ToolError, match="boom"):
        await SendWebhookTool(destinations, FakePoster(ok=False), world.recorder).run(
            {"destination": "lamp", "fields": {"text": "x"}}, _context(world)
        )
    with pytest.raises(ToolError, match="off"):
        await SendWebhookTool(destinations, FakePoster(enabled=False), world.recorder).run(
            {"destination": "lamp", "fields": {"text": "x"}}, _context(world)
        )
