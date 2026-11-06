import json
from pathlib import Path

from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.config.app_config import AppConfig
from aios.config.connector_override import ConnectorOverride
from aios.connectors.code_connector_approval_rule import CodeConnectorApprovalRule
from aios.connectors.code_connector_launcher import CodeConnectorLauncher
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connectors import CodeConnectors
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.crypto_connector_migration import CryptoConnectorMigration
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore

SHIPPED = Path(__file__).parents[2] / "connectors"


def _code(tmp_path: Path, fixed: dict | None = None) -> CodeConnectors:
    overrides = {"crypto": ConnectorOverride(settings=fixed)} if fixed else {}
    return CodeConnectors(
        CodeConnectorLibrary([SHIPPED, tmp_path / "code"]), overrides, tmp_path / "state", "UTC"
    )


async def _catalog(tmp_path: Path, code: CodeConnectors, config: dict) -> ConnectorCatalog:
    store: Collection[Connector] = Collection(
        CollectionDefinition(name="connectors", entity=Connector), InMemoryDocumentStore()
    )
    await store.put(Connector(id="crypto", config=config))
    return ConnectorCatalog(store, [], code=code)


def test_the_library_finds_shipped_and_added_connectors_and_skips_broken_ones(tmp_path) -> None:
    (tmp_path / "code" / "mine").mkdir(parents=True)
    (tmp_path / "code" / "mine" / "connector.yaml").write_text("description: Mine\n")
    (tmp_path / "code" / "broken").mkdir()
    (tmp_path / "code" / "broken" / "connector.yaml").write_text("unknown_key: 1\n")
    (tmp_path / "code" / "escape").mkdir()
    (tmp_path / "code" / "escape" / "connector.yaml").write_text("server: ../../x.py\n")
    names = [m.name for m in _code(tmp_path).library.all()]
    assert "crypto" in names and "mine" in names
    assert "broken" not in names and "escape" not in names


def test_settings_are_defaults_then_the_connector_then_aios_yaml(tmp_path) -> None:
    code = _code(tmp_path, fixed={"max_chf_per_day": 300})
    connector = Connector(
        id="crypto",
        config={"code": "crypto", "settings": {"max_chf_per_day": 900, "min_chf": 20}},
    )
    settings = code.settings(connector)
    assert settings["max_chf_per_day"] == 300  # fixed in aios.yaml wins
    assert settings["min_chf"] == 20  # set on the connector
    assert settings["max_orders_per_day"] == 5  # the manifest's default
    assert code.fixed(connector) == {"max_chf_per_day": 300}


async def test_a_code_connector_starts_with_only_what_it_declares(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KRAKEN_API_KEY", "k")
    code = _code(tmp_path)
    catalog = await _catalog(tmp_path, code, {"code": "crypto"})
    config = catalog.servers()["crypto"]
    assert config["args"][:2] == ["-m", "aios.connectors.code_connector_launcher"]
    assert "k" not in config["args"]  # values travel in the environment only
    env = config["env"]
    assert env["KRAKEN_API_KEY"] == "k"
    assert json.loads(env["AIOS_CONNECTOR_SETTINGS"])["max_chf_per_order"] == 200
    assert set(env["AIOS_CONNECTOR_KEEP"].split(",")) == set(env) - {"AIOS_CONNECTOR_KEEP"}
    assert (tmp_path / "state" / "crypto").is_dir()


async def test_a_connector_naming_a_missing_code_connector_is_left_out(tmp_path) -> None:
    catalog = await _catalog(tmp_path, _code(tmp_path), {"code": "nowhere"})
    assert catalog.servers() == {} and catalog.server_config("crypto") is None


def test_the_launcher_leaves_ai_os_secrets_behind() -> None:
    env = CodeConnectorLauncher.environment(
        {
            "PATH": "/bin",
            "AIOS_SECRETS_KEY": "secret",
            "SLACK_BOT_TOKEN": "xoxb",
            "KRAKEN_API_KEY": "k",
            "AIOS_CONNECTOR_KEEP": "KRAKEN_API_KEY",
        }
    )
    assert env == {"PATH": "/bin", "KRAKEN_API_KEY": "k"}


async def test_a_trade_is_asked_with_the_connectors_words_or_refused_by_it(tmp_path) -> None:
    code = _code(tmp_path)
    rule = CodeConnectorApprovalRule(await _catalog(tmp_path, code, {"code": "crypto"}), code)

    def call(tool: str, chf: object = 50) -> ToolCall:
        return ToolCall(
            tool_name=f"mcp__crypto__{tool}",
            tool_input={"side": "buy", "coin": "btc", "chf": chf},
            user=User(id="u", name="U"),
            conversation_id="c",
        )

    asked = rule.evaluate(call("trade"))
    assert asked.verdict is PolicyVerdict.ASK  # type: ignore[union-attr]
    assert asked.question == "Place a market order on Kraken: buy BTC for 50.00 CHF?"  # type: ignore[union-attr]
    refused = rule.evaluate(call("trade", 1000))
    assert refused.verdict is PolicyVerdict.DENY and "per-order" in refused.reason  # type: ignore[union-attr]
    assert rule.evaluate(call("signal")) is None
    assert (
        rule.evaluate(
            ToolCall(
                tool_name="Read", tool_input={}, user=User(id="u", name="U"), conversation_id="c"
            )
        )
        is None
    )


async def test_the_limits_aios_yaml_fixes_hold_in_the_preflight(tmp_path) -> None:
    code = _code(tmp_path, fixed={"max_chf_per_order": 20})
    rule = CodeConnectorApprovalRule(await _catalog(tmp_path, code, {"code": "crypto"}), code)
    call = ToolCall(
        tool_name="mcp__crypto__trade",
        tool_input={"side": "buy", "coin": "BTC", "chf": 50},
        user=User(id="u", name="U"),
        conversation_id="c",
    )
    assert rule.evaluate(call).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]


def test_the_old_trading_section_becomes_fixed_crypto_settings() -> None:
    config = AppConfig.model_validate(
        {
            "trading": {"max_chf_per_day": 100},
            "connectors": {"crypto": {"settings": {"min_chf": 15}}},
        }
    )
    assert config.connectors["crypto"].settings == {"max_chf_per_day": 100, "min_chf": 15}


async def test_the_migration_moves_grants_and_prompts_to_the_crypto_connector() -> None:
    store = InMemoryDocumentStore()
    agents: Collection[Agent] = Collection(CollectionDefinition(name="agents", entity=Agent), store)
    connectors: Collection[Connector] = Collection(
        CollectionDefinition(name="connectors", entity=Connector), store
    )
    await agents.put(
        Agent(
            id="crypto-trader",
            description="d",
            prompt="Use `crypto_quote`, then `crypto_trade`.\n",
            connectors={"aios": ["crypto_quote", "crypto_trade", "data_query"]},
        )
    )
    await agents.put(
        Agent(id="other", description="d", prompt="p", connectors={"aios": ["read_logs"]})
    )
    migration = CryptoConnectorMigration(agents, connectors)
    await migration.run()
    moved = agents.get("crypto-trader")
    assert moved.connectors == {"aios": ["data_query"], "crypto": ["quote", "trade", "trades"]}  # type: ignore[union-attr]
    assert moved.prompt == "Use `quote`, then `trade`.\n"  # type: ignore[union-attr]
    assert connectors.get("crypto").config == {"code": "crypto"}  # type: ignore[union-attr]
    assert agents.get("other").connectors == {"aios": ["read_logs"]}  # type: ignore[union-attr]
    await migration.run()  # a second start changes nothing
    assert agents.get("crypto-trader") == moved


def test_a_code_connector_brings_its_agents(tmp_path) -> None:
    manifest = _code(tmp_path).library.get("crypto")
    agents = {a.id: a for a in CodeConnectors.agents_of(manifest)}  # type: ignore[arg-type]
    assert agents["crypto-trader"].connectors == {
        "crypto": ["signal", "quote", "trade", "balance", "trades"]
    }
