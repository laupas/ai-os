import json

import pytest

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.skill_catalog import SkillCatalog
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.entities.connectors.connector import Connector
from aios.entities.skills.skill import Skill
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.tools.config_change_approval_rule import ConfigChangeApprovalRule
from aios.tools.config_editor import ConfigEditor
from aios.tools.tool_error import ToolError
from tests.agents.agent_world import AgentWorld

CONFIGURATOR = AgentCatalog.CONFIGURATOR


def _editor(w: AgentWorld) -> ConfigEditor:
    skills: Collection[Skill] = Collection(
        CollectionDefinition(name="skills", entity=Skill), InMemoryDocumentStore()
    )
    return ConfigEditor(w.agents, SkillCatalog(skills), w.connector_store)


def _call(tool: str, agent: str | None = CONFIGURATOR, **tool_input: object) -> ToolCall:
    return ToolCall(
        tool_name=f"mcp__aios__{tool}",
        tool_input=tool_input,
        user=User(id="alice", name="Alice"),
        conversation_id="c",
        agent=agent,
    )


def test_only_the_configurator_may_use_the_config_tools() -> None:
    rule = ConfigChangeApprovalRule()
    for agent in ("orchestrator", "scheduler", None):
        decision = rule.evaluate(_call("config_list", agent=agent, kind="agents"))
        assert decision is not None and decision.verdict is PolicyVerdict.DENY
    decision = rule.evaluate(_call("config_list", kind="agents"))
    assert decision is not None and decision.verdict is PolicyVerdict.ALLOW
    assert rule.evaluate(_call("data_put", collection="schedules")) is None


def test_every_change_asks_an_administrator_with_the_document() -> None:
    rule = ConfigChangeApprovalRule()
    put = rule.evaluate(_call("config_put", kind="agents", document={"id": "x", "prompt": "Do X"}))
    assert put is not None and put.verdict is PolicyVerdict.ASK
    assert put.approver_permission is Permission.ADMINISTER
    assert '"Do X"' in put.question and "agents" in put.question
    delete = rule.evaluate(_call("config_delete", kind="skills", name="old"))
    assert delete is not None and delete.verdict is PolicyVerdict.ASK
    assert '"old"' in delete.question


async def test_saves_go_through_the_catalog_checks(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    editor = _editor(w)
    await editor.save("agents", {"id": "weather", "description": "Weather.", "prompt": "Weather."})
    assert w.agents.get("weather") is not None
    with pytest.raises(ToolError, match="lower-case"):
        await editor.save("agents", {"id": "Bad_Name", "description": "x", "prompt": "x"})
    messenger = editor.get("agents", "messenger")
    with pytest.raises(ToolError, match="fixed"):
        await editor.save("agents", {**messenger, "enabled": False})
    with pytest.raises(ToolError, match="fixed"):
        await editor.delete("agents", "orchestrator")
    with pytest.raises(ToolError, match="does not fit"):
        await editor.save("skills", {"id": "s"})


async def test_connectors_are_saved_but_the_builtin_one_is_not(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    editor = _editor(w)
    await editor.save("connectors", {"id": "gcal", "config": {"command": "npx"}})
    assert [c["id"] for c in editor.list("connectors")] == ["gcal"]
    with pytest.raises(ToolError, match="built-in"):
        await editor.save("connectors", {"id": "aios", "config": {}})
    await editor.delete("connectors", "gcal")
    assert w.connector_store.get("gcal") is None


async def test_unknown_kinds_and_names_are_reported(tmp_path) -> None:
    editor = _editor(AgentWorld(tmp_path))
    with pytest.raises(ToolError, match="kind"):
        editor.list("users")
    with pytest.raises(ToolError, match="no agents entry"):
        editor.get("agents", "nobody")
    assert json.dumps(editor.list("agents"))  # plain JSON


def test_the_configurator_is_fixed(tmp_path) -> None:
    assert AgentWorld(tmp_path).agents.is_fixed(CONFIGURATOR)


def test_connector_entity_needs_no_more_than_id_and_config() -> None:
    assert Connector.model_validate({"id": "x", "config": {}}).enabled
