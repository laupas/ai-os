import subprocess

from aios.agents.repo_agent_reader import RepoAgentReader
from aios.agents.repo_skill_reader import RepoSkillReader
from aios.config.settings import Settings
from aios.config_repo.config_repo_bootstrap import ConfigRepoBootstrap
from aios.config_repo.config_repo_initializer import ConfigRepoInitializer
from aios.entities.agents.agent import Agent
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from tests.config_repo.repo_world import RepoWorld


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _initializer(w: RepoWorld, tmp_path, collections=None):  # type: ignore[no-untyped-def]
    return ConfigRepoInitializer(
        w.store,
        w.legacy,
        collections or [*w.collections, w.roles],
        RepoAgentReader(tmp_path / "no-seed"),
        RepoSkillReader(tmp_path / "no-seed"),
        {},
        legacy_config=tmp_path / "data" / "config.yaml",
    )


async def test_a_new_repository_takes_config_yaml_in_its_first_commit(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.yaml").write_text("channels: [web]\n")
    await _initializer(w, tmp_path).run()
    assert (w.root / "aios.yaml").read_text() == "channels: [web]\n"
    assert not (tmp_path / "data" / "config.yaml").exists()
    assert (tmp_path / "data" / "config.yaml.moved-to-repository").exists()
    assert len(w.log(".")) == 1


async def test_roles_move_into_an_older_repository_once(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    await _initializer(w, tmp_path, w.collections).run()  # an older version: no roles
    (w.root / ".aios-imported").unlink()  # older versions wrote no marker either
    git("-C", str(w.root), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "older")
    owner = Role(id="owner", name="Owner", permissions={Permission.ADMINISTER})
    await w.legacy.put("roles", "owner", owner.model_dump(mode="json"))
    await _initializer(w, tmp_path).run()
    assert w.roles.get("owner") == owner and (w.root / "roles" / "owner.yaml").exists()
    await w.roles.delete("owner")
    await _initializer(w, tmp_path).run()
    await w.roles.load()
    assert w.roles.get("owner") is None  # imported once, never again


async def test_a_new_machine_clones_its_whole_configuration(tmp_path, monkeypatch) -> None:
    old = RepoWorld(tmp_path / "old")
    (tmp_path / "old" / "data").mkdir(parents=True)
    (tmp_path / "old" / "data" / "config.yaml").write_text("channels: [slack, web]\n")
    await _initializer(old, tmp_path / "old").run()
    await old.agents.put(Agent(id="weather", description="Weather.", prompt="Say it.\n"))
    bare = tmp_path / "github.git"
    git("clone", "--quiet", "--bare", str(old.root), str(bare))

    new_data = tmp_path / "new"
    monkeypatch.setenv("AIOS_DATA_DIR", str(new_data))
    monkeypatch.setenv("AIOS_CONFIG_REMOTE", str(bare))
    settings = Settings()
    ConfigRepoBootstrap(settings).run()
    assert settings.resolved_config_file() == new_data / "config" / "aios.yaml"
    assert settings.resolved_config_file().read_text() == "channels: [slack, web]\n"
    assert (new_data / "config" / "agents" / "weather.md").exists()


async def test_an_existing_repository_gets_config_yaml_moved_in(tmp_path, monkeypatch) -> None:
    from aios.config_repo.current_author import AIOS
    from aios.config_repo.git_repository import GitRepository

    data = tmp_path / "data"
    repo = GitRepository(data / "config")
    repo.init()
    (repo.root / "x").write_text("x")
    repo.commit(["x"], "first", AIOS)
    (data / "config.yaml").write_text("channels: [web]\n")
    monkeypatch.setenv("AIOS_DATA_DIR", str(data))
    ConfigRepoBootstrap(Settings()).run()
    assert (repo.root / "aios.yaml").read_text() == "channels: [web]\n"
    assert "aios.yaml: moved in" in git("-C", str(repo.root), "log", "-1", "--format=%s")
    assert (data / "config.yaml.moved-to-repository").exists()
