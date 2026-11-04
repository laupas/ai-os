import subprocess

from aios.agents.repo_agent_reader import RepoAgentReader
from aios.agents.repo_skill_reader import RepoSkillReader
from aios.config_repo.config_repo_initializer import ConfigRepoInitializer
from aios.config_repo.config_repo_watcher import ConfigRepoWatcher
from aios.entities.schedules.schedule import Schedule
from tests.config_repo.repo_world import RepoWorld


def _seed(tmp_path):  # type: ignore[no-untyped-def]
    (tmp_path / "seed" / "agents").mkdir(parents=True)
    (tmp_path / "seed" / "agents" / "general.md").write_text(
        "---\nname: general\ndescription: Answers.\ntools: WebSearch\n---\nAnswer.\n"
    )
    (tmp_path / "seed" / "skills" / "voice").mkdir(parents=True)
    (tmp_path / "seed" / "skills" / "voice" / "SKILL.md").write_text(
        "---\nname: voice\ndescription: Voice.\n---\n\nBe brief.\n"
    )


def _initializer(w: RepoWorld, tmp_path) -> ConfigRepoInitializer:  # type: ignore[no-untyped-def]
    return ConfigRepoInitializer(
        w.store,
        w.legacy,
        w.collections,
        RepoAgentReader(tmp_path / "seed" / "agents"),
        RepoSkillReader(tmp_path / "seed" / "skills"),
        {"gcal": {"command": "npx", "env": {"T": "${TOKEN}"}}},
    )


async def test_the_first_start_takes_old_data_else_the_seed_in_one_commit(tmp_path) -> None:
    _seed(tmp_path)
    w = RepoWorld(tmp_path)
    old = Schedule(id="s1", name="brief", prompt="Brief me.", cron=["0 7 * * *"], user_id="u")
    older_shape = {
        **old.model_dump(mode="json", exclude={"user_id"}),
        "channel": "slack",
        "run_as_user_id": "u",
    }
    await w.legacy.put("schedules", "s1", older_shape)
    await _initializer(w, tmp_path).run()
    assert w.agents.get("general").builtin_tools == ["WebSearch"]  # type: ignore[union-attr]
    assert w.skills.get("voice").content == "Be brief.\n"  # type: ignore[union-attr]
    assert w.connectors.get("gcal").config["env"]["T"] == "${TOKEN}"  # type: ignore[union-attr]
    assert w.schedules.get("s1").prompt == "Brief me."  # type: ignore[union-attr]
    assert len(w.log(".")) == 1
    assert "channel" not in (w.root / "schedules" / "s1.yaml").read_text()
    await w.schedules.put(w.schedules.get("s1"))  # type: ignore[arg-type]
    assert len(w.log(".")) == 1  # nothing left for a later save to rewrite
    assert w.store.last_head == w.repo.head()


async def test_an_existing_repository_is_left_alone(tmp_path) -> None:
    _seed(tmp_path)
    w = RepoWorld(tmp_path)
    await _initializer(w, tmp_path).run()
    await w.agents.delete("general")
    await _initializer(w, tmp_path).run()
    await w.agents.load()
    assert w.agents.get("general") is None


async def test_an_outside_commit_is_picked_up_and_a_broken_one_ignored(tmp_path) -> None:
    _seed(tmp_path)
    w = RepoWorld(tmp_path)
    await _initializer(w, tmp_path).run()
    watcher = ConfigRepoWatcher(w.store, w.collections)
    general = w.root / "agents" / "general.md"
    general.write_text(general.read_text().replace("Answer.", "Answer in German."))
    await watcher.check()
    assert w.agents.get("general").prompt == "Answer.\n"  # type: ignore[union-attr]  # not committed

    def commit(message: str) -> None:
        git = ["git", "-C", str(w.root), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "commit", "-qam", message], check=True)

    commit("outside")
    await watcher.check()
    assert w.agents.get("general").prompt == "Answer in German.\n"  # type: ignore[union-attr]
    general.write_text("---\ndescription: [broken\n---\nx\n")
    commit("broken")
    await watcher.check()
    assert w.agents.get("general").prompt == "Answer in German.\n"  # type: ignore[union-attr]
