from aios.config_repo.change_author import ChangeAuthor
from aios.config_repo.current_author import CurrentAuthor
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.users.permission import Permission
from tests.web.console import ALICE, BOB, Console


async def _manager(c: Console) -> None:
    """Bob may manage agents and has one connector of his own; gcal is admins only."""
    await c.grant("member", Permission.MANAGE_AGENTS)
    await c.agent_world.add_gcal()
    await c.agent_world.connector_store.put(
        Connector(id="weather", config={"command": "npx"}, available_to=["group:member"])
    )


async def _create(c: Console, **fields: object):  # type: ignore[no-untyped-def]
    body = {"name": "helper", "description": "Helps.", "prompt": "Help.", **fields}
    return await c.client.post("/api/agents", json=body, headers=c.headers(BOB, write=True))


async def test_a_manager_sees_only_what_they_may_grant(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _manager(c)
        data = await (await c.client.get("/api/agents", headers=c.headers(BOB))).json()
        assert [x["name"] for x in data["connectors"]] == ["weather"]
        assert data["builtin_tools"] == []
        assert [g["id"] for g in data["groups"]] == ["member"]
        admin = await (await c.client.get("/api/agents", headers=c.headers(ALICE))).json()
        assert {"aios", "gcal", "weather"} <= {x["name"] for x in admin["connectors"]}


async def test_a_manager_grants_only_within_their_own_reach(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _manager(c)
        ok = await _create(c, connectors={"weather": None}, available_to=["group:member"])
        assert ok.status == 201
        refused = [
            await _create(c, name="a", connectors={"gcal": None}),
            await _create(c, name="b", connectors={"aios": ["data_query"]}),
            await _create(c, name="c", builtin_tools=["WebSearch"]),
            await _create(c, name="d", available_to=["group:owner"]),
        ]
        assert [r.status for r in refused] == [403, 403, 403, 403]
        assert (await _create(c, name="e", available_to=["everyone"])).status == 201


async def test_a_manager_leaves_fixed_agents_alone(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _manager(c)
        h = c.headers(BOB, write=True)
        r = await c.client.put("/api/agents/messenger", json={"prompt": "x"}, headers=h)
        assert r.status == 403
        assert (await c.client.delete("/api/agents/messenger", headers=h)).status != 200


async def test_what_an_administrator_granted_stays_when_a_manager_edits(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _manager(c)
        await c.agent_world.update(
            "calendar",
            builtin_tools=["WebSearch"],
            connectors={"gcal": None},
            available_to=["group:owner"],
        )
        h = c.headers(BOB, write=True)
        current = c.agent_world.agents.get("calendar")
        assert current is not None
        body = {**current.model_dump(exclude={"id"}), "prompt": "Better.\n"}
        assert (await c.client.put("/api/agents/calendar", json=body, headers=h)).status == 200
        saved = c.agent_world.agents.get("calendar")
        assert saved is not None and saved.prompt == "Better.\n"
        assert saved.connectors == {"gcal": None} and saved.builtin_tools == ["WebSearch"]
        # Widening what was granted on gcal is a new grant, and refused.
        widened = await c.client.put(
            "/api/agents/calendar", json={"connectors": {"gcal": ["x"]}}, headers=h
        )
        assert widened.status == 403
        # Taking a grant away is fine.
        r = await c.client.put("/api/agents/calendar", json={"connectors": {}}, headers=h)
        assert r.status == 200


async def test_skill_managers_read_the_agents_but_do_not_change_them(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.grant("member", Permission.MANAGE_SKILLS)
        assert (await c.client.get("/api/agents", headers=c.headers(BOB))).status == 200
        assert (await _create(c)).status == 403
        body = {"name": "tone", "description": "Tone.", "content": "Be kind."}
        r = await c.client.post("/api/skills", json=body, headers=c.headers(BOB, write=True))
        assert r.status == 201


async def test_a_manager_reads_an_agents_history_but_only_an_admin_restores_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.grant("member", Permission.MANAGE_AGENTS)
        CurrentAuthor.set(ChangeAuthor(name="Alice", email=ALICE))
        first = Agent(id="weather", description="Weather.", prompt="Say the weather.\n")
        await c.repo_world.agents.put(first)
        await c.repo_world.agents.put(first.model_copy(update={"prompt": "Other.\n"}))
        log = await c.client.get("/api/history/agents/weather", headers=c.headers(BOB))
        assert log.status == 200
        oldest = (await log.json())["commits"][-1]["commit"]
        r = await c.client.post(
            "/api/history/agents/weather/restore",
            json={"commit": oldest},
            headers=c.headers(BOB, write=True),
        )
        assert r.status == 403
        triggers = await c.client.get("/api/history/triggers/x", headers=c.headers(BOB))
        assert triggers.status == 403


async def test_administer_brings_every_managing_right(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.grant("member", Permission.ADMINISTER)
        bob = c.world.users.get("bob")
        assert bob is not None
        assert Permission.ADMINISTER.implied <= c.world.authorizer.permissions_of(bob)
        assert (await c.client.get("/api/variables", headers=c.headers(BOB))).status == 200


async def test_logs_and_variables_have_rights_of_their_own(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await c.client.get("/api/logs", headers=c.headers(BOB))).status == 403
        assert (await c.client.get("/api/variables", headers=c.headers(BOB))).status == 403
        await c.grant("member", Permission.VIEW_LOGS, Permission.MANAGE_VARIABLES)
        assert (await c.client.get("/api/logs", headers=c.headers(BOB))).status == 200
        assert (await c.client.get("/api/variables", headers=c.headers(BOB))).status == 200
        assert (await c.client.get("/api/settings", headers=c.headers(BOB))).status == 403
