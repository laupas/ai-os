from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.engine.agent_definitions_builder import AgentDefinitionsBuilder
from aios.entities.connectors.connector import Connector
from tests.agents.agent_world import AgentWorld
from tests.fakes.fake_clock import FakeClock


async def test_env_references_are_filled_in_only_when_started(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GMAIL_KEY", "secret")
    w = AgentWorld(tmp_path)
    await w.connector_store.put(Connector(id="gmail", config={"env": {"K": "${GMAIL_KEY}"}}))
    await w.connector_store.put(Connector(id="off", config={}, enabled=False))
    assert w.connectors.servers() == {"gmail": {"env": {"K": "secret"}}}
    assert w.connectors.tool_prefixes() == ["mcp__aios__", "mcp__gmail__"]


def test_the_board_reads_tools_and_status_from_the_init_message() -> None:
    board = ConnectorStatusBoard(FakeClock())
    board.record(
        {
            "tools": ["Task", "mcp__gcal__list-events", "mcp__aios__ask_human"],
            "mcp_servers": [
                {"name": "gcal", "status": "connected"},
                {"name": "x", "status": "failed"},
            ],
        }
    )
    assert board.tools_of("gcal") == ["list-events"]
    assert board.get("x").status == "failed"  # type: ignore[union-attr]
    assert board.tools_of("x") is None


async def test_subagents_see_only_their_granted_tools(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.add_gcal()
    board = ConnectorStatusBoard(FakeClock())
    builder = AgentDefinitionsBuilder(w.agents, w.connectors, board)
    definitions = builder.build()
    assert set(definitions) == {"calendar", "messenger"}
    assert definitions["messenger"].tools == ["Skill", "mcp__aios__send_message"]
    assert definitions["messenger"].skills == ["message-style"]
    assert builder.skills(w.agents.orchestrator(), delegating=True) == ["message-style"]
    assert builder.skills(w.agents.orchestrator(), delegating=False) == []
    # A whole connector whose tools nobody has seen yet: visibility is left to the gate.
    await w.update("calendar", connectors={"gcal": None})
    assert builder.build()["calendar"].tools is None
    board.record({"tools": ["mcp__gcal__a", "mcp__gcal__b"], "mcp_servers": [{"name": "gcal"}]})
    assert builder.build()["calendar"].tools == ["mcp__gcal__a", "mcp__gcal__b"]
