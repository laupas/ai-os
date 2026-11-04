from datetime import UTC, datetime

from aios.config_repo.change_author import ChangeAuthor
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.agents.agent import Agent
from aios.entities.schedules.schedule import Schedule
from aios.entities.skills.skill import Skill
from tests.config_repo.repo_world import RepoWorld


async def test_an_agent_is_a_markdown_file_and_every_change_a_commit(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    CurrentAuthor.set(ChangeAuthor(name="Alice", email="alice@example.com"))
    agent = Agent(id="weather", description="Weather.", prompt="Say the weather.\n", model="haiku")
    await w.agents.put(agent)
    text = (w.root / "agents" / "weather.md").read_text()
    assert text.startswith("---\ndescription: Weather.\nmodel: haiku\n")
    assert text.endswith("---\n\nSay the weather.\n")
    await w.agents.put(agent.model_copy(update={"prompt": "Say it briefly.\n"}))
    await w.agents.put(agent.model_copy(update={"prompt": "Say it briefly.\n"}))  # no change
    log = w.log("agents/weather.md")
    assert [e["subject"] for e in log] == ["agents/weather: update", "agents/weather: add"]
    assert log[0]["author"] == "Alice"
    await w.agents.delete("weather")
    assert w.log("agents/weather.md")[0]["subject"] == "agents/weather: delete"


async def test_files_read_back_into_the_same_documents(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    agent = Agent(
        id="calendar",
        description="Calendar.",
        prompt="Manage it.\n",
        builtin_tools=["WebSearch"],
        connectors={"gcal": None, "aios": ["ask_human"]},
    )
    await w.agents.put(agent)
    await w.skills.put(Skill(id="voice", description="Voice.", content="Be brief.\n"))
    assert (w.root / "skills" / "voice" / "SKILL.md").read_text().startswith("---\nname: voice\n")
    await w.agents.load()
    await w.skills.load()
    assert w.agents.get("calendar") == agent
    assert w.skills.get("voice") == Skill(id="voice", description="Voice.", content="Be brief.\n")


async def test_a_schedule_firing_changes_no_file(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    schedule = Schedule(
        id="brief", name="brief", prompt="Brief me.", cron=["0 7 * * *"], user_id="u"
    )
    await w.schedules.put(schedule)
    fired = datetime(2026, 11, 2, 7, tzinfo=UTC)
    await w.schedules.put(schedule.model_copy(update={"last_fired_at": fired}))
    assert len(w.log("schedules/brief.yaml")) == 1
    assert "last_fired_at" not in (w.root / "schedules" / "brief.yaml").read_text()
    await w.schedules.load()
    assert w.schedules.get("brief").last_fired_at == fired  # type: ignore[union-attr]


async def test_an_unreadable_file_is_skipped(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    w.repo.init()
    (w.root / "connectors").mkdir()
    (w.root / "connectors" / "bad.yaml").write_text("config: [unclosed\n")
    assert await w.store.list("connectors") == []
