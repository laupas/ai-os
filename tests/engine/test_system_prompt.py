from datetime import UTC, datetime

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.repo_agent_reader import RepoAgentReader
from aios.common.clock import Clock
from aios.config.app_config_loader import AppConfigLoader
from aios.engine.system_prompt_builder import SystemPromptBuilder
from aios.engine.turn_request import TurnRequest
from aios.entities.agents.agent import Agent
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.memories.memory import Memory
from aios.entities.memories.memory_kind import MemoryKind
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore


class _Clock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def test_prompt_has_local_time_and_only_preferences(tmp_path) -> None:
    (tmp_path / "orchestrator.md").write_text("---\nname: orchestrator\n---\nYou are ai-os.\n")
    store = InMemoryDocumentStore()
    memories: Collection[Memory] = Collection(
        CollectionDefinition(name="memories", entity=Memory), store
    )
    stored: Collection[Agent] = Collection(CollectionDefinition(name="agents", entity=Agent), store)
    for agent in RepoAgentReader(tmp_path).read():
        await stored.put(agent)
    agents = AgentCatalog(stored)
    await memories.put(Memory(id="1", kind=MemoryKind.PREFERENCE, subject="Signoff", text="P."))
    await memories.put(Memory(id="2", kind=MemoryKind.NOTE, text="secret journal"))
    builder = SystemPromptBuilder(agents, _Clock(), "Europe/Zurich", memories)
    now = datetime(2026, 10, 9, tzinfo=UTC)
    prompt = builder.build(
        TurnRequest(
            conversation=Conversation(id="c", created_at=now, updated_at=now),
            user=User(id="u1", name="Alice"),
            binding=ChannelBinding(channel="slack", address="D1", thread="1"),
            text="hi",
        )
    )
    assert prompt.startswith("You are ai-os.")
    assert "Friday 2026-10-09 14:00 (Europe/Zurich)" in prompt
    assert "- Signoff: P." in prompt and "secret journal" not in prompt
    assert "user id u1" in prompt and "address D1" in prompt


def test_config_keeps_env_references_in_mcp_servers(tmp_path, monkeypatch) -> None:
    # They are copied into the connectors and must not carry the secret itself.
    monkeypatch.setenv("GMAIL_DIR", "/data/google")
    (tmp_path / "config.yaml").write_text(
        "mcp_servers:\n  gmail: {command: npx, env: {P: '${GMAIL_DIR}/keys.json'}}\n"
    )
    config = AppConfigLoader(tmp_path / "config.yaml").load()
    assert config.mcp_servers["gmail"]["env"]["P"] == "${GMAIL_DIR}/keys.json"
