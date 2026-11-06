from datetime import UTC, datetime

from aios.approvals.rule_based_approval_policy import RuleBasedApprovalPolicy
from aios.config.agent_config import AgentConfig
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.engine.agent_definitions_builder import AgentDefinitionsBuilder
from aios.engine.claude_options_factory import ClaudeOptionsFactory
from aios.engine.system_prompt_builder import SystemPromptBuilder
from aios.engine.tool_permission_gate import ToolPermissionGate
from aios.engine.turn_request import TurnRequest
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.memories.memory import Memory
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.tools.aios_tool_server import AiosToolServer
from tests.agents.agent_world import AgentWorld
from tests.fakes.fake_clock import FakeClock
from tests.fakes.world import World


async def _options(tmp_path, agent: str | None):  # type: ignore[no-untyped-def]
    w = AgentWorld(tmp_path)
    world = await World().setup()
    memories: Collection[Memory] = Collection(
        CollectionDefinition(name="memories", entity=Memory), InMemoryDocumentStore()
    )
    factory = ClaudeOptionsFactory(
        AgentConfig(model="opus"),
        tmp_path,
        SystemPromptBuilder(w.agents, FakeClock(), "Europe/Zurich", memories),
        AiosToolServer([]),
        ToolPermissionGate(RuleBasedApprovalPolicy([]), world.approval_service),
        w.agents,
        w.connectors,
        AgentDefinitionsBuilder(w.agents, w.connectors, ConnectorStatusBoard(FakeClock())),
    )
    now = datetime.now(UTC)
    conversation = Conversation(id="c", agent=agent, created_at=now, updated_at=now)
    return factory.create(
        TurnRequest(
            conversation=conversation,
            user=User(id="u", name="P"),
            binding=ChannelBinding(channel="web", address="a", thread="t"),
            text="hi",
        ),
        None,
    )


async def test_the_orchestrator_runs_the_turn_and_offers_the_agents(tmp_path) -> None:
    options = await _options(tmp_path, None)
    assert set(options.agents or {}) == {"calendar", "messenger"}
    assert str(options.system_prompt).startswith("You orchestrate.")
    assert options.model == "opus" and options.allowed_tools == []


async def test_subagents_run_in_the_turn_not_in_the_background(tmp_path) -> None:
    options = await _options(tmp_path, None)
    assert options.env["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] == "1"


async def test_a_chosen_agent_runs_the_turn_itself_without_subagents(tmp_path) -> None:
    options = await _options(tmp_path, "messenger")
    assert options.agents == {}
    assert str(options.system_prompt).startswith("You send messages.")
    assert options.model == "sonnet"  # the agent's own model
    assert options.skills == ["message-style"]
