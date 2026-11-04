from aios.config_repo.change_author import ChangeAuthor
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.agents.agent import Agent
from tests.web.console import ALICE, BOB, Console


async def test_an_agent_has_a_history_and_an_old_version_comes_back(tmp_path) -> None:
    async with Console(tmp_path) as c:
        rw = c.repo_world
        CurrentAuthor.set(ChangeAuthor(name="Alice", email=ALICE))
        first = Agent(id="weather", description="Weather.", prompt="Say the weather.\n")
        await rw.agents.put(first)
        await rw.agents.put(first.model_copy(update={"prompt": "Broken prompt.\n"}))
        h = c.headers(ALICE, write=True)
        assert (
            await c.client.get("/api/history/agents/weather", headers=c.headers(BOB))
        ).status == 403
        data = await (await c.client.get("/api/history/agents/weather", headers=h)).json()
        newest, oldest = data["commits"]
        assert newest["author"] == "Alice" and data["path"] == "agents/weather.md"
        diff = await (
            await c.client.get(f"/api/history/agents/weather/{newest['commit']}", headers=h)
        ).json()
        assert "-Say the weather." in diff["diff"] and "+Broken prompt." in diff["diff"]
        r = await c.client.post(
            "/api/history/agents/weather/restore", json={"commit": oldest["commit"]}, headers=h
        )
        assert r.status == 200
        assert rw.agents.get("weather").prompt == "Say the weather.\n"  # type: ignore[union-attr]
        assert (
            len(
                (await (await c.client.get("/api/history/agents/weather", headers=h)).json())[
                    "commits"
                ]
            )
            == 3
        )


async def test_bad_names_and_commits_are_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        assert (await c.client.get("/api/history/users/x", headers=h)).status == 404
        assert (await c.client.get("/api/history/agents/..", headers=h)).status in (400, 404)
        bad = await c.client.get("/api/history/agents/weather/HEAD~1", headers=h)
        assert bad.status == 400
        missing = await c.client.post(
            "/api/history/agents/nope/restore", json={"commit": "abcdef1"}, headers=h
        )
        assert missing.status == 404
