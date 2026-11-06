import pytest

from aios.config_repo.config_branches import ConfigBranches
from aios.config_repo.config_repo_watcher import ConfigRepoWatcher
from aios.config_repo.repository_conflict import RepositoryConflict
from aios.config_repo.repository_file_check import RepositoryFileCheck
from aios.config_repo.repository_files import RepositoryFiles
from aios.entities.agents.agent import Agent
from tests.config_repo.repo_world import RepoWorld

WEATHER = Agent(id="weather", description="Weather.", prompt="Say the weather.\n")
AGENT_FILE = "agents/weather.md"


async def _world(tmp_path):  # type: ignore[no-untyped-def]
    w = RepoWorld(tmp_path)
    w.repo.init()
    await w.agents.put(WEATHER)
    watcher = ConfigRepoWatcher(w.store, w.collections)
    files = RepositoryFiles(w.store, watcher, RepositoryFileCheck(w.store, w.collections))
    return w, files


async def test_the_tree_and_a_file_of_the_branch(tmp_path) -> None:
    _, files = await _world(tmp_path)
    tree = await files.tree("main")
    assert [f["path"] for f in tree] == [AGENT_FILE]
    file = await files.read("main", AGENT_FILE)
    assert "Say the weather." in file["text"] and file["blob"] == tree[0]["blob"]
    assert not file["binary"]


async def test_a_save_is_a_commit_in_the_callers_name_and_applies_at_once(tmp_path) -> None:
    w, files = await _world(tmp_path)
    opened = await files.read("main", AGENT_FILE)
    text = opened["text"].replace("Say the weather.", "Say the weather, briefly.")
    commit = await files.write("main", AGENT_FILE, text, opened["blob"], "Shorter")
    assert commit is not None
    assert w.agents.get("weather").prompt == "Say the weather, briefly.\n"  # type: ignore[union-attr]
    (latest,) = await files.history("main", AGENT_FILE, 0, 1)
    assert latest["subject"] == "Shorter" and latest["files"] == [("M", AGENT_FILE)]


async def test_a_file_the_configuration_could_not_load_is_refused(tmp_path) -> None:
    w, files = await _world(tmp_path)
    opened = await files.read("main", AGENT_FILE)
    broken = "---\nmodel: sonnet\n---\n\nNo description.\n"
    with pytest.raises(ValueError, match="description"):
        await files.write("main", AGENT_FILE, broken, opened["blob"], "")
    with pytest.raises(ValueError):
        await files.write("main", "aios.yaml", "web: {enabled: maybe}\n", None, "")
    with pytest.raises(ValueError):
        await files.write("main", "code/x/server.py", "def (:\n", None, "")
    with pytest.raises(ValueError):
        await files.write("main", "code/x/connector.yaml", "unknown: 1\n", None, "")
    assert w.agents.get("weather") == WEATHER


async def test_a_file_changed_since_it_was_opened_is_not_overwritten(tmp_path) -> None:
    w, files = await _world(tmp_path)
    opened = await files.read("main", AGENT_FILE)
    await w.agents.put(WEATHER.model_copy(update={"description": "Changed meanwhile."}))
    with pytest.raises(RepositoryConflict):
        await files.write("main", AGENT_FILE, opened["text"], opened["blob"], "")
    with pytest.raises(RepositoryConflict):  # a "new" file that exists
        await files.write("main", AGENT_FILE, opened["text"], None, "")


async def test_another_branch_is_written_beside_the_running_one(tmp_path) -> None:
    w, files = await _world(tmp_path)
    await ConfigBranches(w.store, w.collections).create("draft", None)
    opened = await files.read("draft", AGENT_FILE)
    text = opened["text"].replace("Say the weather.", "Draft.")
    await files.write("draft", AGENT_FILE, text, opened["blob"], "On the draft")
    assert "Draft." in (await files.read("draft", AGENT_FILE))["text"]
    assert "Say the weather." in (await files.read("main", AGENT_FILE))["text"]
    assert w.agents.get("weather") == WEATHER
    assert w.repo.current_branch() == "main" and w.repo.is_clean()


async def test_new_files_and_deleting_them(tmp_path) -> None:
    w, files = await _world(tmp_path)
    await files.write("main", "code/hello/server.py", "print('hi')\n", None, "Add hello")
    assert (w.root / "code/hello/server.py").read_text() == "print('hi')\n"
    blob = (await files.read("main", "code/hello/server.py"))["blob"]
    await files.write("main", "code/hello/server.py", None, blob, "")
    assert not (w.root / "code/hello/server.py").exists()
    with pytest.raises(ValueError, match="cannot be deleted"):
        await files.write("main", "aios.yaml", None, None, "")


@pytest.mark.parametrize("path", ["../outside", ".git/config", "/etc/passwd", "a//b", ""])
def test_a_path_outside_the_repository_is_refused(path: str) -> None:
    with pytest.raises(ValueError):
        RepositoryFileCheck.path(path)


async def test_an_unknown_branch_or_ref_is_refused(tmp_path) -> None:
    _, files = await _world(tmp_path)
    with pytest.raises(ValueError):
        await files.tree("--output=/tmp/x")
    with pytest.raises(ValueError, match="no branch"):
        await files.write("nope", "x.yaml", "a: 1\n", None, "")


async def test_what_is_local_and_what_is_on_the_remote(tmp_path) -> None:
    w, files = await _world(tmp_path)
    assert await files.remote("main") == {"configured": False}
    origin = tmp_path / "origin.git"
    w.repo._git("init", "--bare", "--quiet", str(origin))  # noqa: SLF001 - a remote for the test
    w.repo.set_remote(str(origin))
    status = await files.remote("main")
    assert status["configured"] and not status["on_remote"]  # never pushed
    w.repo.push({}, "main")
    w.repo.fetch({})
    assert (await files.remote("main"))["unpushed"] == []
    opened = await files.read("main", AGENT_FILE)
    commit = await files.write("main", AGENT_FILE, opened["text"] + "More.\n", opened["blob"], "")
    status = await files.remote("main")
    assert status["on_remote"] and status["unpushed"] == [commit] and status["behind"] == 0
    assert status["fetched_at"] is not None
