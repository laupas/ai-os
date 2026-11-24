from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.engine.agent_definitions_builder import AgentDefinitionsBuilder
from aios.entities.connectors.connector import Connector
from aios.entities.users.user import User
from tests.agents.agent_world import AgentWorld
from tests.fakes.fake_clock import FakeClock
from tests.fakes.open_audience import OpenAudience

USER = User(id="u", name="U")


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
    builder = AgentDefinitionsBuilder(w.agents, w.connectors, board, OpenAudience())
    definitions = builder.build(USER)
    assert set(definitions) == {"calendar", "messenger"}
    assert definitions["messenger"].tools == ["Skill", "mcp__aios__send_message"]
    assert definitions["messenger"].skills == ["message-style"]
    assert builder.skills(w.agents.orchestrator(), delegating=True, user=USER) == ["message-style"]
    assert builder.skills(w.agents.orchestrator(), delegating=False, user=USER) == []
    # A whole connector whose tools nobody has seen yet: visibility is left to the gate.
    await w.update("calendar", connectors={"gcal": None})
    assert builder.build(USER)["calendar"].tools is None
    board.record({"tools": ["mcp__gcal__a", "mcp__gcal__b"], "mcp_servers": [{"name": "gcal"}]})
    assert builder.build(USER)["calendar"].tools == ["mcp__gcal__a", "mcp__gcal__b"]


def test_tool_names_outlive_a_restart_but_the_status_does_not(tmp_path) -> None:
    file = tmp_path / "connector-tools.json"
    board = ConnectorStatusBoard(FakeClock(), file)
    board.record(
        {
            "tools": ["mcp__gmail__send_email", "mcp__gmail__search"],
            "mcp_servers": [{"name": "gmail", "status": "connected"}],
        }
    )
    board.set("homey", "connected", ["get_devices"])
    later = ConnectorStatusBoard(FakeClock(), file)
    assert later.tools_of("gmail") == ["search", "send_email"]
    assert later.tools_of("homey") == ["get_devices"]
    assert later.get("gmail") is None


def test_an_unreadable_tools_file_is_learnt_again(tmp_path) -> None:
    file = tmp_path / "connector-tools.json"
    file.write_text("{not json")
    board = ConnectorStatusBoard(FakeClock(), file)
    assert board.tools_of("gmail") is None
    board.set("gmail", "connected", ["search"])
    assert ConnectorStatusBoard(FakeClock(), file).tools_of("gmail") == ["search"]
