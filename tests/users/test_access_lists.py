from datetime import UTC, datetime

import pytest

from aios.agents.agent_grant_rule import AgentGrantRule
from aios.agents.agent_unavailable_error import AgentUnavailableError
from aios.approvals.rule_based_approval_policy import RuleBasedApprovalPolicy
from aios.approvals.tool_call import ToolCall
from aios.config.agent_config import AgentConfig
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.engine.agent_definitions_builder import AgentDefinitionsBuilder
from aios.engine.claude_credentials import ClaudeCredentials
from aios.engine.claude_options_factory import ClaudeOptionsFactory
from aios.engine.system_prompt_builder import SystemPromptBuilder
from aios.engine.tool_permission_gate import ToolPermissionGate
from aios.engine.turn_request import TurnRequest
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.memories.memory import Memory
from aios.entities.users.group import Group
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.tools.aios_tool_server import AiosToolServer
from aios.users.access_lists_migration import MIGRATIONS, AccessListsMigration
from aios.users.permission_audience import PermissionAudience
from tests.agents.agent_world import AgentWorld
from tests.config_repo.repo_world import RepoWorld
from tests.fakes.fake_clock import FakeClock
from tests.fakes.world import World


async def _world(tmp_path):  # type: ignore[no-untyped-def]
    """Alice owns ai-os; Bob is a member, and in the group `family`."""
    world = await World().setup()
    await world.groups.put(Group(id="family", name="Family"))
    bob = world.bob.model_copy(update={"group_ids": ["member", "family"]})
    await world.users.put(bob)
    alice = world.users.get(world.alice.id)
    return world, alice, bob, PermissionAudience(world.authorizer)


async def test_an_audience_is_everyone_or_groups_and_always_the_administrators(
    tmp_path,
) -> None:
    world, alice, bob, audience = await _world(tmp_path)
    assert audience.includes(alice, None)  # administrators always
    assert not audience.includes(bob, None)  # no list: administrators only
    assert not audience.includes(bob, [])
    assert audience.includes(bob, ["everyone"])
    assert audience.includes(bob, ["group:family"])
    assert audience.includes(bob, ["group:member"])
    assert not audience.includes(bob, ["group:work"])
    assert not audience.includes(None, ["everyone"])


def _factory(tmp_path, w: AgentWorld, world: World, audience) -> ClaudeOptionsFactory:  # type: ignore[no-untyped-def]
    memories: Collection[Memory] = Collection(
        CollectionDefinition(name="memories", entity=Memory), InMemoryDocumentStore()
    )

    class Resolver:
        def value_of(self, name: str) -> str | None:
            return "oauth"

    return ClaudeOptionsFactory(
        lambda: AgentConfig(model="opus"),
        tmp_path,
        SystemPromptBuilder(w.agents, FakeClock(), lambda: "Europe/Zurich", memories),
        AiosToolServer([]),
        ToolPermissionGate(RuleBasedApprovalPolicy([]), world.approval_service),
        w.agents,
        w.connectors,
        AgentDefinitionsBuilder(
            w.agents, w.connectors, ConnectorStatusBoard(FakeClock()), audience
        ),
        ClaudeCredentials(lambda: "subscription", Resolver()),  # type: ignore[arg-type]
        audience,
    )


def _request(user: User, agent: str | None) -> TurnRequest:
    now = datetime.now(UTC)
    return TurnRequest(
        conversation=Conversation(id="c", agent=agent, created_at=now, updated_at=now),
        user=user,
        binding=ChannelBinding(channel="web", address="a", thread="t"),
        text="hi",
    )


async def test_a_turn_holds_only_what_is_available_to_its_user(tmp_path) -> None:
    world, alice, bob, audience = await _world(tmp_path)
    w = AgentWorld(tmp_path)
    await w.connector_store.put(Connector(id="gcal", config={"command": "npx"}))
    await w.update("messenger", available_to=["group:family"])
    factory = _factory(tmp_path, w, world, audience)

    mine = factory.create(_request(bob, None), None)
    assert set(mine.agents or {}) == {"messenger"}  # calendar: administrators only
    assert "gcal" not in mine.mcp_servers  # type: ignore[operator]

    theirs = factory.create(_request(alice, None), None)
    assert set(theirs.agents or {}) == {"calendar", "messenger"}
    assert "gcal" in theirs.mcp_servers  # type: ignore[operator]

    with pytest.raises(AgentUnavailableError, match="not available"):
        factory.create(_request(bob, "calendar"), None)
    factory.create(_request(bob, "messenger"), None)  # his group's

    await w.connector_store.put(
        Connector(id="gcal", config={"command": "npx"}, available_to=["group:family"])
    )
    assert "gcal" in factory.create(_request(bob, None), None).mcp_servers  # type: ignore[operator]


async def test_a_call_past_the_options_is_still_refused(tmp_path) -> None:
    world, alice, bob, audience = await _world(tmp_path)
    w = AgentWorld(tmp_path)
    await w.add_gcal()
    rule = AgentGrantRule(w.agents, w.connectors, audience)

    def call(tool: str, agent: str, user: User, **tool_input: object) -> ToolCall:
        return ToolCall(
            tool_name=tool, tool_input=dict(tool_input), user=user, conversation_id="c", agent=agent
        )

    refused = rule.evaluate(call("mcp__gcal__list-events", "calendar", bob))
    assert refused is not None and "not available to" in refused.reason
    assert rule.evaluate(call("mcp__gcal__list-events", "calendar", alice)) is None
    delegated = rule.evaluate(call("Task", "orchestrator", bob, subagent_type="calendar"))
    assert delegated is not None and "calendar is not available" in delegated.reason
    await w.update("calendar", available_to=["everyone"])
    gone = rule.evaluate(call("mcp__gcal__list-events", "calendar", bob))
    assert gone is not None and "connector gcal is not available" in gone.reason


async def test_existing_items_stay_available_to_everyone_once(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    await w.agents.put(Agent(id="old", description="", prompt="p"))
    await w.connectors.put(Connector(id="local", config={"command": "npx"}))
    migration = AccessListsMigration(w.store, w.agents, w.connectors)
    await migration.run()
    assert w.agents.get("old").available_to == ["everyone"]  # type: ignore[union-attr]
    assert w.connectors.get("local").available_to == ["everyone"]  # type: ignore[union-attr]
    assert "access-lists" in (w.store.read_file(MIGRATIONS) or "")
    await w.agents.put(Agent(id="new", description="", prompt="p"))
    await migration.run()
    assert w.agents.get("new").available_to is None  # made later: administrators only


async def test_a_repository_seeded_with_lists_is_only_marked(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    await w.agents.put(Agent(id="memory", description="", prompt="p", available_to=["everyone"]))
    await w.agents.put(Agent(id="log-checker", description="", prompt="p"))
    await AccessListsMigration(w.store, w.agents, w.connectors).run()
    assert w.agents.get("log-checker").available_to is None  # type: ignore[union-attr]
    assert "access-lists" in (w.store.read_file(MIGRATIONS) or "")
