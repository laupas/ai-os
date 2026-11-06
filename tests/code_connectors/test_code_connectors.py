import json
import os
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.config.app_config import AppConfig
from aios.config.connector_override import ConnectorOverride
from aios.connectors.code_connector_approval_rule import CodeConnectorApprovalRule
from aios.connectors.code_connector_launcher import CodeConnectorLauncher
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connectors import CodeConnectors
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.entities.connectors.connector import Connector
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore

FIXTURE = Path(__file__).parent / "fixture"


def _code(tmp_path: Path, fixed: dict | None = None) -> CodeConnectors:
    overrides = {"echo": ConnectorOverride(settings=fixed)} if fixed else {}
    return CodeConnectors(
        CodeConnectorLibrary([FIXTURE, tmp_path / "code"]), overrides, tmp_path / "state", "UTC"
    )


async def _catalog(code: CodeConnectors, config: dict) -> ConnectorCatalog:
    store: Collection[Connector] = Collection(
        CollectionDefinition(name="connectors", entity=Connector), InMemoryDocumentStore()
    )
    await store.put(Connector(id="echo", config=config))
    return ConnectorCatalog(store, [], code=code)


def _call(tool: str, text: str) -> ToolCall:
    return ToolCall(
        tool_name=f"mcp__echo__{tool}",
        tool_input={"text": text},
        user=User(id="u", name="U"),
        conversation_id="c",
    )


def test_the_library_finds_connectors_and_skips_broken_ones(tmp_path) -> None:
    (tmp_path / "code" / "mine").mkdir(parents=True)
    (tmp_path / "code" / "mine" / "connector.yaml").write_text("description: Mine\n")
    (tmp_path / "code" / "broken").mkdir()
    (tmp_path / "code" / "broken" / "connector.yaml").write_text("unknown_key: 1\n")
    (tmp_path / "code" / "escape").mkdir()
    (tmp_path / "code" / "escape" / "connector.yaml").write_text("server: ../../x.py\n")
    names = [m.name for m in _code(tmp_path).library.all()]
    assert names == ["echo", "mine"]


def test_settings_are_defaults_then_the_connector_then_aios_yaml(tmp_path) -> None:
    code = _code(tmp_path, fixed={"max_length": 3})
    connector = Connector(
        id="echo", config={"code": "echo", "settings": {"max_length": 50, "greeting": "hi"}}
    )
    assert code.settings(connector) == {"greeting": "hi", "max_length": 3}
    assert code.fixed(connector) == {"max_length": 3}


async def test_a_code_connector_starts_with_only_what_it_declares(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ECHO_TOKEN", "t")
    catalog = await _catalog(_code(tmp_path), {"code": "echo"})
    config = catalog.servers()["echo"]
    assert config["args"][:2] == ["-m", "aios.connectors.code_connector_launcher"]
    assert "t" not in config["args"]  # values travel in the environment only
    env = config["env"]
    assert env["ECHO_TOKEN"] == "t"
    assert json.loads(env["AIOS_CONNECTOR_SETTINGS"]) == {"greeting": "hello", "max_length": 10}
    assert set(env["AIOS_CONNECTOR_KEEP"].split(",")) == set(env) - {"AIOS_CONNECTOR_KEEP"}
    assert (tmp_path / "state" / "echo").is_dir()


async def test_the_server_runs_and_sees_none_of_ai_os_s_secrets(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-secret")
    monkeypatch.setenv("ECHO_TOKEN", "t")
    config = (await _catalog(_code(tmp_path), {"code": "echo"})).servers()["echo"]
    # Claude Code starts a server with its own environment, which is ai-os's.
    params = StdioServerParameters(
        command=config["command"], args=config["args"], env={**os.environ, **config["env"]}
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        assert {t.name for t in (await session.list_tools()).tools} == {"echo", "shout"}
        answer = json.loads((await session.call_tool("echo", {"text": "you"})).content[0].text)
    assert answer["text"] == "hello you"
    assert "SLACK_BOT_TOKEN" not in answer["env"] and "ECHO_TOKEN" in answer["env"]
    assert not list((FIXTURE / "echo").glob("__pycache__"))  # nothing written beside it


async def test_a_connector_naming_a_missing_code_connector_is_left_out(tmp_path) -> None:
    catalog = await _catalog(_code(tmp_path), {"code": "nowhere"})
    assert catalog.servers() == {} and catalog.server_config("echo") is None


def test_the_launcher_leaves_ai_os_secrets_behind() -> None:
    env = CodeConnectorLauncher.environment(
        {
            "PATH": "/bin",
            "AIOS_SECRETS_KEY": "secret",
            "SLACK_BOT_TOKEN": "xoxb",
            "ECHO_TOKEN": "t",
            "AIOS_CONNECTOR_KEEP": "ECHO_TOKEN",
        }
    )
    assert env == {"PATH": "/bin", "ECHO_TOKEN": "t", "PYTHONDONTWRITEBYTECODE": "1"}


async def test_a_call_is_asked_in_the_connectors_words_or_refused_by_it(tmp_path) -> None:
    code = _code(tmp_path)
    rule = CodeConnectorApprovalRule(await _catalog(code, {"code": "echo"}), code)
    asked = rule.evaluate(_call("shout", "hi"))
    assert asked.verdict is PolicyVerdict.ASK and asked.question == "Shout 'hi'?"  # type: ignore[union-attr]
    refused = rule.evaluate(_call("shout", "far too long a text"))
    assert refused.verdict is PolicyVerdict.DENY and "too long" in refused.reason  # type: ignore[union-attr]
    assert rule.evaluate(_call("echo", "hi")) is None
    assert rule.evaluate(_call("echo", "hi").model_copy(update={"tool_name": "Read"})) is None


async def test_what_aios_yaml_fixes_holds_in_the_preflight(tmp_path) -> None:
    code = _code(tmp_path, fixed={"max_length": 1})
    rule = CodeConnectorApprovalRule(await _catalog(code, {"code": "echo"}), code)
    assert rule.evaluate(_call("shout", "hi")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]


def test_the_old_trading_section_is_refused_rather_than_dropped() -> None:
    with pytest.raises(ValueError, match="code connector"):
        AppConfig.model_validate({"trading": {"max_chf_per_day": 100}})


def test_a_code_connector_brings_its_agents(tmp_path) -> None:
    manifest = _code(tmp_path).library.get("echo")
    (agent,) = CodeConnectors.agents_of(manifest)  # type: ignore[arg-type]
    assert agent.id == "echo-agent" and agent.connectors == {"echo": ["echo", "shout"]}
