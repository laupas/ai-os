import asyncio
import base64
import subprocess

import pytest

import aios.config_repo.config_remote as config_remote
from aios.config_repo.branch_error import BranchError
from aios.config_repo.config_remote import ConfigRemote
from aios.entities.agents.agent import Agent
from aios.entities.git.git_remote import GitRemote
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.variables.secret_box import SecretBox
from tests.config_repo.repo_world import RepoWorld
from tests.fakes.fake_clock import FakeClock

WEATHER = Agent(id="weather", description="Weather.", prompt="Say the weather.\n")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


async def _world(tmp_path, auto_push: bool = False):  # type: ignore[no-untyped-def]
    bare = tmp_path / "remote.git"
    git("init", "--bare", "--quiet", "--initial-branch=main", str(bare))
    w = RepoWorld(tmp_path)
    w.repo.init()
    remotes: Collection[GitRemote] = Collection(
        CollectionDefinition(name="git-remotes", entity=GitRemote), InMemoryDocumentStore()
    )
    box = SecretBox("k" * 64, tmp_path / "unused.key")
    remote = ConfigRemote(
        w.store, remotes, box, FakeClock(), tmp_path / "known_hosts", w.collections
    )
    # A local bare repository stands in for GitHub; save() only takes real addresses.
    await remotes.put(GitRemote(url=str(bare), auth="none", auto_push=auto_push))
    w.repo.set_remote(str(bare))
    await w.agents.put(WEATHER)
    return w, remote, bare


async def test_every_branch_is_pushed_and_its_standing_known(tmp_path) -> None:
    w, remote, bare = await _world(tmp_path)
    w.repo.create_branch("experiment", "main")
    result = await remote.push(None)
    assert result.ok and "main" in result.message and "experiment" in result.message
    assert "main" in git("-C", str(bare), "branch") and "experiment" in git(
        "-C", str(bare), "branch"
    )
    await w.agents.put(WEATHER.model_copy(update={"prompt": "Newer.\n"}))
    await remote.fetch()
    assert remote.branch_status()["main"] == {"ahead": 1, "behind": 0}
    assert (await remote.push("main")).ok and (
        await remote.push("main")
    ).message == "everything was already there"


async def test_auto_push_follows_each_commit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_remote, "AUTO_PUSH_DELAY", 0)
    w, remote, bare = await _world(tmp_path, auto_push=True)
    await w.agents.put(WEATHER.model_copy(update={"prompt": "Pushed by itself.\n"}))
    for _ in range(50):
        await asyncio.sleep(0.05)
        if "Pushed by itself" in git("-C", str(bare), "show", "main:agents/weather.md"):
            break
    assert "Pushed by itself" in git("-C", str(bare), "show", "main:agents/weather.md")


async def test_a_pull_brings_in_what_was_pushed_elsewhere_and_reloads(tmp_path) -> None:
    w, remote, bare = await _world(tmp_path)
    await remote.push(None)
    other = tmp_path / "laptop"
    git("clone", "--quiet", str(bare), str(other))
    path = other / "agents" / "weather.md"
    path.write_text(path.read_text().replace("Say the weather.", "Say it from the laptop."))
    git("-C", str(other), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "laptop")
    git("-C", str(other), "push", "--quiet", "origin", "main")
    assert await remote.pull("main") == []
    assert w.agents.get("weather").prompt == "Say it from the laptop.\n"  # type: ignore[union-attr]


async def test_a_conflicting_pull_is_undone(tmp_path) -> None:
    w, remote, bare = await _world(tmp_path)
    await remote.push(None)
    other = tmp_path / "laptop"
    git("clone", "--quiet", str(bare), str(other))
    (other / "agents" / "weather.md").write_text("---\ndescription: x\n---\n\nLaptop.\n")
    git("-C", str(other), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "laptop")
    git("-C", str(other), "push", "--quiet", "origin", "main")
    await w.agents.put(WEATHER.model_copy(update={"prompt": "Here.\n"}))
    assert await remote.pull("main") == ["agents/weather.md"]
    assert w.repo.is_clean() and w.agents.get("weather").prompt == "Here.\n"  # type: ignore[union-attr]


async def test_keys_and_tokens_are_kept_encrypted_and_never_in_argv(tmp_path) -> None:
    w, remote, _ = await _world(tmp_path)
    public = await remote.generate_key("Alice")
    assert public.startswith("ssh-ed25519 ") and public.endswith(" ai-os")
    stored = remote.settings()
    assert stored is not None and "OPENSSH PRIVATE KEY" not in (stored.private_key or "")
    await remote.save(
        "https://github.com/laupas/ai-os-config.git", "token", "ghp_secret", False, "Alice"
    )
    assert "ghp_secret" not in (remote.settings().token or "")  # type: ignore[union-attr]
    with remote._env(remote.settings()) as env:  # type: ignore[arg-type]
        header = env["GIT_CONFIG_VALUE_0"]
    assert base64.b64decode(header.split()[-1]).decode() == "x-access-token:ghp_secret"
    with pytest.raises(BranchError):
        await remote.save("git@github.com:laupas/x.git", "token", None, False, "Alice")
    with pytest.raises(BranchError):
        await remote.save("https://github.com/laupas/x.git", "ssh", None, False, "Alice")
    with pytest.raises(BranchError):
        await remote.save("not a url", "ssh", None, False, "Alice")
