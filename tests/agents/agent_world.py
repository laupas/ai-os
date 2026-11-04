from pathlib import Path

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_grant_rule import AgentGrantRule
from aios.agents.repo_agent_reader import RepoAgentReader
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore

ORCHESTRATOR = """---
name: orchestrator
description: Main thread.
tools: Task, WebSearch, mcp__aios__ask_human
---
You orchestrate.
"""
MESSENGER = """---
name: messenger
description: Sends messages.
tools: mcp__aios__send_message, Skill
skills: message-style
model: sonnet
---
You send messages.
"""
CALENDAR = """---
name: calendar
description: Calendar.
tools: mcp__gcal__list-events, mcp__gcal__create-event
---
You manage the calendar.
"""


class AgentWorld:
    """An agent catalog holding three agents read from files the way the seed reads
    them, and a connector catalog where `gcal` can be added."""

    def __init__(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        for name, text in [
            ("orchestrator", ORCHESTRATOR),
            ("messenger", MESSENGER),
            ("calendar", CALENDAR),
        ]:
            (agents_dir / f"{name}.md").write_text(text)
        store = InMemoryDocumentStore()
        self.store: Collection[Agent] = Collection(
            CollectionDefinition(name="agents", entity=Agent), store
        )
        for agent in RepoAgentReader(agents_dir).read():
            self.store._items[agent.id] = agent  # as if loaded; tests may be sync
        self.connector_store: Collection[Connector] = Collection(
            CollectionDefinition(name="connectors", entity=Connector), store
        )
        self.agents = AgentCatalog(self.store)
        self.connectors = ConnectorCatalog(
            self.connector_store, ["ask_human", "send_message", "data_query"]
        )
        self.rule = AgentGrantRule(self.agents, self.connectors)

    async def add_gcal(self, enabled: bool = True) -> None:
        await self.connector_store.put(
            Connector(id="gcal", config={"command": "npx"}, enabled=enabled)
        )

    async def update(self, name: str, **fields: object) -> Agent:
        """Changes some fields of an agent, as the console does."""
        agent = self.agents.get(name)
        assert agent is not None
        return await self.agents.save(agent.model_copy(update=fields))
