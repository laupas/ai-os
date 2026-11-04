import pytest

from aios.agents.agent_unavailable_error import AgentUnavailableError
from aios.agents.catalog_error import CatalogError
from aios.entities.agents.agent import Agent
from tests.agents.agent_world import AgentWorld


def test_seed_files_become_agents_with_their_grants(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    messenger = w.agents.get("messenger")
    assert messenger is not None
    assert messenger.connectors == {"aios": ["send_message"]}
    assert messenger.skills == ["message-style"]
    assert messenger.builtin_tools == []  # Skill is granted by name, not as a tool
    assert messenger.model == "sonnet" and w.agents.is_fixed("messenger")
    assert w.agents.orchestrator().prompt == "You orchestrate.\n"


def test_the_orchestrator_is_listed_first_and_never_a_delegate(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert [a.id for a in w.agents.all()] == ["orchestrator", "calendar", "messenger"]
    assert [a.id for a in w.agents.delegates()] == ["calendar", "messenger"]


async def test_a_switched_off_agent_is_no_delegate(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.update("calendar", enabled=False)
    assert "calendar" not in [a.id for a in w.agents.delegates()]


async def test_a_fixed_agent_cannot_be_switched_off_or_deleted(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    with pytest.raises(CatalogError):
        await w.update("messenger", enabled=False)
    with pytest.raises(CatalogError):
        await w.agents.delete("orchestrator")
    disabled = w.agents.orchestrator().model_copy(update={"enabled": False})
    await w.store.put(disabled)  # written behind the catalog's back
    assert w.agents.orchestrator().enabled


async def test_any_other_agent_can_be_deleted(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    await w.agents.delete("calendar")
    assert w.agents.get("calendar") is None


async def test_an_agent_needs_a_slug_a_description_and_a_prompt(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    with pytest.raises(CatalogError):
        await w.agents.save(Agent(id="travel", description="Trips", prompt=" "))
    with pytest.raises(CatalogError):
        await w.agents.save(Agent(id="Not OK", description="x", prompt="y"))
    await w.agents.save(Agent(id="travel", description="Trips", prompt="Plan trips."))
    assert w.agents.get("travel") is not None


async def test_the_main_agent_is_the_orchestrator_unless_one_is_chosen(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    assert w.agents.main(None).id == "orchestrator"
    assert w.agents.main("calendar").id == "calendar"
    with pytest.raises(AgentUnavailableError):
        w.agents.main("nobody")
    await w.update("calendar", enabled=False)
    with pytest.raises(AgentUnavailableError):
        w.agents.main("calendar")


async def test_a_prompt_can_list_the_enabled_agents(tmp_path) -> None:
    w = AgentWorld(tmp_path)
    travel = await w.agents.save(
        Agent(id="travel", description="Plans trips.", prompt="Pick one of:\n{{agents}}\n")
    )
    await w.update("calendar", enabled=False)
    prompt = w.agents.prompt_of(travel)
    assert "- `travel`: Plans trips." in prompt and "- `messenger`: Sends messages." in prompt
    assert "calendar" not in prompt and "{{agents}}" not in prompt
