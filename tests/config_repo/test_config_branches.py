import pytest

from aios.config_repo.branch_error import BranchError
from aios.config_repo.config_branches import ConfigBranches
from aios.entities.agents.agent import Agent
from tests.config_repo.repo_world import RepoWorld

WEATHER = Agent(id="weather", description="Weather.", prompt="Say the weather.\n")


async def _world(tmp_path):  # type: ignore[no-untyped-def]
    w = RepoWorld(tmp_path)
    w.repo.init()
    await w.agents.put(WEATHER)
    return w, ConfigBranches(w.store, w.collections)


async def test_a_branch_is_a_version_ai_os_switches_to_and_back(tmp_path) -> None:
    w, branches = await _world(tmp_path)
    await branches.create("experiment", None)
    await branches.switch("experiment")
    await w.agents.put(WEATHER.model_copy(update={"prompt": "Say it in German.\n"}))
    overview = await branches.overview()
    assert overview["current"] == "experiment"
    assert {b["name"]: b["current"] for b in overview["branches"]} == {
        "experiment": True,
        "main": False,
    }
    await branches.switch("main")
    assert w.agents.get("weather").prompt == "Say the weather.\n"  # type: ignore[union-attr]
    main = next(b for b in (await branches.overview())["branches"] if b["name"] == "experiment")
    assert (main["ahead"], main["behind"]) == (1, 0)
    assert (await branches.compare("experiment"))["files"] == [
        {"status": "M", "path": "agents/weather.md"}
    ]


async def test_a_merge_into_another_branch_leaves_the_running_one_alone(tmp_path) -> None:
    w, branches = await _world(tmp_path)
    await branches.create("experiment", None)
    await branches.create("staging", None)
    await branches.switch("experiment")
    await w.agents.put(WEATHER.model_copy(update={"prompt": "Say it in German.\n"}))
    await branches.switch("main")
    assert await branches.merge("experiment", "staging") == []  # in a worktree
    assert w.agents.get("weather").prompt == "Say the weather.\n"  # type: ignore[union-attr]
    assert await branches.merge("experiment", "main") == []  # the running branch: reloaded
    assert w.agents.get("weather").prompt == "Say it in German.\n"  # type: ignore[union-attr]
    assert w.repo.is_clean()


async def test_a_conflicting_merge_is_undone_and_names_its_files(tmp_path) -> None:
    w, branches = await _world(tmp_path)
    await branches.create("experiment", None)
    await w.agents.put(WEATHER.model_copy(update={"prompt": "On main.\n"}))
    await branches.switch("experiment")
    await w.agents.put(WEATHER.model_copy(update={"prompt": "On the branch.\n"}))
    await branches.switch("main")
    assert await branches.merge("experiment", "main") == ["agents/weather.md"]
    assert w.repo.is_clean() and w.agents.get("weather").prompt == "On main.\n"  # type: ignore[union-attr]


async def test_main_and_the_running_branch_are_kept_and_names_are_checked(tmp_path) -> None:
    w, branches = await _world(tmp_path)
    await branches.create("feature/x", None)
    with pytest.raises(BranchError):
        await branches.delete("main", False)
    await branches.switch("feature/x")
    with pytest.raises(BranchError):
        await branches.delete("feature/x", False)
    await w.agents.put(WEATHER.model_copy(update={"prompt": "Unmerged.\n"}))
    await branches.switch("main")
    with pytest.raises(BranchError):
        await branches.delete("feature/x", False)  # unmerged work
    await branches.delete("feature/x", True)
    for bad in ("../x", "a b", "-x", "x.lock"):
        with pytest.raises(BranchError):
            await branches.create(bad, None)


async def test_switching_is_refused_over_uncommitted_edits(tmp_path) -> None:
    w, branches = await _world(tmp_path)
    await branches.create("experiment", None)
    (w.root / "agents" / "weather.md").write_text("edited by hand, not committed\n")
    with pytest.raises(BranchError):
        await branches.switch("experiment")
