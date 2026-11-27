from aios.config.store_config import TEMPLATES
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from tests.store.store_source_world import commit_change, make_source
from tests.web.console import ALICE, BOB, Console


async def _with_source(c: Console, tmp_path) -> str:
    (tmp_path / "source").mkdir()
    url = make_source(tmp_path / "source")
    response = await c.client.post(
        "/api/store/sources", json={"url": url}, headers=c.headers(ALICE, write=True)
    )
    assert response.status == 201, await response.text()
    return url


async def _install(c: Console, url: str, kind: str, item: str, **fields: object):
    body = {"source": url, "kind": kind, "id": item, **fields}
    headers = c.headers(ALICE, write=True)
    return await c.client.post("/api/store/install", json=body, headers=headers)


def _item(state: dict, kind: str, item: str) -> dict:
    return next(i for i in state["items"] if i["kind"] == kind and i["id"] == item)


async def test_a_source_lists_its_items_and_what_they_need(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        state = await (await c.client.get("/api/store", headers=c.headers(ALICE))).json()
        [source] = state["sources"]
        assert (source["url"], source["name"], source["error"]) == (url, "Test templates", None)
        assert [p.split(":")[0] for p in source["problems"]] == ["agents/broken.md"]
        cal = _item(state, "agent", "cal")
        assert (cal["title"], cal["category"], cal["installed"]) == ("Calendar", "Google", False)
        assert {(r["id"], r["installed"], r["in_source"]) for r in cal["requires"]} == {
            ("gcal", False, True),
            ("message-style", True, False),
        }
        assert [v["variable"] for v in cal["variables"]] == ["GCAL_ID", "GCAL_SECRET"]
        assert _item(state, "connector", "hello")["code"] is True


async def test_installing_an_agent_brings_its_connector_and_the_variables(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        values = {"GCAL_ID": "client-1", "GCAL_SECRET": "s3cret"}
        response = await _install(c, url, "agent", "cal", variables=values)
        assert response.status == 200, await response.text()
        result = await response.json()
        assert result["installed"] == ["connector:gcal", "agent:cal"]
        assert result["kept"] == ["skill:message-style"]
        assert c.agent_world.agents.get("cal").connectors == {"gcal": None}
        assert c.agent_world.connector_store.get("gcal").config["headers"] == {
            "X-Client": "${GCAL_ID}",
            "Authorization": "Bearer ${GCAL_SECRET}",
        }
        assert c.variables.get("GCAL_SECRET").secret
        assert c.variable_resolver.value_of("GCAL_SECRET") == "s3cret"
        assert c.variable_resolver.value_of("GCAL_ID") == "client-1"


async def test_an_installed_item_is_replaced_only_when_asked(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        assert (await _install(c, url, "agent", "cal")).status == 200
        assert (await _install(c, url, "agent", "cal")).status == 409
        await c.agent_world.connector_store.put(Connector(id="gcal", config={"command": "mine"}))
        assert (await _install(c, url, "agent", "cal", replace=True)).status == 200
        # A requirement that is there is never overwritten.
        assert c.agent_world.connector_store.get("gcal").config == {"command": "mine"}


async def test_a_trigger_is_the_installing_users_under_a_new_id(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        first = await (await _install(c, url, "trigger", "brief")).json()
        assert first["installed"] == ["connector:gcal", "agent:cal", "trigger:brief"]
        assert (await _install(c, url, "trigger", "brief")).status == 200
        triggers = c.triggers.all()
        assert len(triggers) == 2 and len({t.id for t in triggers}) == 2
        assert {(t.user_id, t.agent) for t in triggers} == {("alice", "cal")}


async def test_a_code_connector_needs_trust_and_lands_in_the_repository(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        refused = await _install(c, url, "connector", "hello")
        assert refused.status == 400
        assert "program" in await refused.text()
        response = await _install(c, url, "connector", "hello", trust_code=True)
        assert response.status == 200, await response.text()
        installed = (await response.json())["installed"]
        assert installed[0] == "connector:hello" and installed[1:]  # and its own agents
        root = c.repo_world.root
        assert (root / "code" / "hello-world" / "server.py").is_file()
        assert (root / "code" / "hello-world" / "connector.yaml").is_file()
        assert not list(root.rglob("__pycache__"))
        log = c.repo_world.repo.log("code/hello-world/server.py")
        assert [e["subject"] for e in log][:1] == ["Store: install connector hello"]


async def test_a_variable_the_item_does_not_ask_for_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        response = await _install(c, url, "agent", "cal", variables={"OTHER": "x"})
        assert response.status == 400
        assert c.agent_world.agents.get("cal") is None


async def test_sources_are_added_and_removed_in_aios_yaml(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        assert url in c.config_file.read_text()
        assert [s.url for s in c.live_config.current().store.sources] == [TEMPLATES, url]
        bad = await c.client.post(
            "/api/store/sources", json={"url": "ftp://x"}, headers=c.headers(ALICE, write=True)
        )
        assert bad.status == 400
        again = await c.client.post(
            "/api/store/sources", json={"url": url}, headers=c.headers(ALICE, write=True)
        )
        assert again.status == 409
        gone = await c.client.delete(
            "/api/store/sources", json={"url": url}, headers=c.headers(ALICE, write=True)
        )
        assert gone.status == 200
        assert (await gone.json())["sources"] == []
        assert [s.url for s in c.live_config.current().store.sources] == [TEMPLATES]


async def test_a_source_that_cannot_be_fetched_says_why(tmp_path) -> None:
    async with Console(tmp_path) as c:
        missing = (tmp_path / "nowhere").as_uri()
        response = await c.client.post(
            "/api/store/sources", json={"url": missing}, headers=c.headers(ALICE, write=True)
        )
        [source] = (await response.json())["sources"]
        assert "git clone failed" in source["error"]


async def test_the_store_is_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await c.client.get("/api/store", headers=c.headers(BOB))).status == 403


async def test_an_item_knows_its_installed_version_and_offers_an_update(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        cal = _item(
            await (await c.client.get("/api/store", headers=c.headers(ALICE))).json(),
            "agent",
            "cal",
        )
        assert (cal["version"], cal["author"], cal["license"]) == ("1.0.0", "Tester", "MIT")
        assert (cal["homepage"], cal["tags"]) == ("https://cal.example", ["google", "calendar"])
        assert (cal["installed_version"], cal["update_available"]) == (None, False)
        assert (await (await _install(c, url, "agent", "cal")).json())["version"] == "1.0.0"

        commit_change(tmp_path / "source", "agents/cal.md", "'1.0.0'", "'1.2.0'")
        state = await (
            await c.client.post("/api/store/refresh", headers=c.headers(ALICE, write=True))
        ).json()
        cal = _item(state, "agent", "cal")
        assert (cal["version"], cal["installed_version"], cal["installed_from"]) == (
            "1.2.0",
            "1.0.0",
            url,
        )
        assert cal["update_available"] is True

        assert (await _install(c, url, "agent", "cal", replace=True)).status == 200
        state = await (await c.client.get("/api/store", headers=c.headers(ALICE))).json()
        cal = _item(state, "agent", "cal")
        assert (cal["installed_version"], cal["update_available"]) == ("1.2.0", False)
        records = (c.repo_world.root / ".aios-store.yaml").read_text()
        assert "agent:cal" in records and "connector:gcal" in records


async def test_installed_versions_are_listed_for_the_pages_of_each_kind(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        assert (await _install(c, url, "agent", "cal")).status == 200
        rows = await (await c.client.get("/api/store/installed", headers=c.headers(ALICE))).json()
        assert (rows["agent:cal"]["version"], rows["agent:cal"]["source"]) == ("1.0.0", url)
        assert rows["agent:cal"]["latest"] is None
        assert "connector:gcal" in rows

        commit_change(tmp_path / "source", "agents/cal.md", "'1.0.0'", "'1.2.0'")
        await c.client.post("/api/store/refresh", headers=c.headers(ALICE, write=True))
        rows = await (await c.client.get("/api/store/installed", headers=c.headers(ALICE))).json()
        assert rows["agent:cal"]["latest"] == "1.2.0"

        await c.agent_world.agents.delete("cal")
        rows = await (await c.client.get("/api/store/installed", headers=c.headers(ALICE))).json()
        assert "agent:cal" not in rows
        assert (await c.client.get("/api/store/installed", headers=c.headers(BOB))).status == 403


async def test_an_item_made_by_hand_has_no_installed_version(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _with_source(c, tmp_path)
        await c.agent_world.connector_store.put(Connector(id="gcal", config={"command": "mine"}))
        state = await (await c.client.get("/api/store", headers=c.headers(ALICE))).json()
        gcal = _item(state, "connector", "gcal")
        assert (gcal["installed"], gcal["installed_version"], gcal["update_available"]) == (
            True,
            None,
            False,
        )


async def _uninstall(c: Console, kind: str, item: str):
    body = {"kind": kind, "id": item}
    headers = c.headers(ALICE, write=True)
    return await c.client.post("/api/store/uninstall", json=body, headers=headers)


async def test_uninstall_removes_the_item_and_its_record_but_keeps_what_it_brought(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        await _install(c, url, "agent", "cal", variables={"GCAL_ID": "client-1"})
        response = await _uninstall(c, "agent", "cal")
        assert response.status == 200, await response.text()
        assert await response.json() == {"removed": ["agent:cal"], "still_used_by": []}
        assert c.agent_world.agents.get("cal") is None
        assert c.agent_world.connector_store.get("gcal") is not None
        assert c.variable_resolver.value_of("GCAL_ID") == "client-1"
        records = (c.repo_world.root / ".aios-store.yaml").read_text()
        assert "agent:cal" not in records and "connector:gcal" in records
        state = await (await c.client.get("/api/store", headers=c.headers(ALICE))).json()
        assert _item(state, "agent", "cal")["installed"] is False


async def test_uninstalling_a_connector_says_who_still_uses_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        await _install(c, url, "agent", "cal")
        state = await (await c.client.get("/api/store", headers=c.headers(ALICE))).json()
        # The test world's own calendar agent is granted gcal too.
        both = ["agent:calendar", "agent:cal"]
        assert sorted(_item(state, "connector", "gcal")["used_by"]) == sorted(both)
        result = await (await _uninstall(c, "connector", "gcal")).json()
        assert result["removed"] == ["connector:gcal"]
        assert sorted(result["still_used_by"]) == sorted(both)


async def test_uninstalling_a_code_connector_removes_its_code(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        await _install(c, url, "connector", "hello", trust_code=True)
        result = await (await _uninstall(c, "connector", "hello")).json()
        assert result["removed"][0] == "connector:hello"
        assert "code/hello-world/server.py" in result["removed"]
        assert not (c.repo_world.root / "code" / "hello-world").exists()
        log = c.repo_world.repo.log("code/hello-world/server.py")
        assert log[0]["subject"] == "Store: uninstall connector hello"


async def test_core_agents_and_what_is_not_there_cannot_be_uninstalled(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _with_source(c, tmp_path)
        assert (await _uninstall(c, "agent", "orchestrator")).status == 400
        assert (await _uninstall(c, "agent", "cal")).status == 400
        assert (await _uninstall(c, "trigger", "brief")).status == 400
        assert c.agent_world.agents.get("orchestrator") is not None


async def test_a_connector_installs_again_under_another_name_with_its_own_variables(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        assert (await _install(c, url, "connector", "gcal")).status == 200
        values = {"GCAL_ID": "work-client", "GCAL_SECRET": "work-secret"}
        response = await _install(c, url, "connector", "gcal", name="gcal-work", variables=values)
        assert response.status == 200, await response.text()
        assert (await response.json())["installed"] == ["connector:gcal-work"]
        copy = c.agent_world.connector_store.get("gcal-work")
        assert copy.config["headers"] == {
            "X-Client": "${GCAL_WORK_GCAL_ID}",
            "Authorization": "Bearer ${GCAL_WORK_GCAL_SECRET}",
        }
        assert c.variable_resolver.value_of("GCAL_WORK_GCAL_SECRET") == "work-secret"
        assert c.variable_resolver.value_of("GCAL_SECRET") is None
        assert c.agent_world.connector_store.get("gcal").config["headers"]["X-Client"] == (
            "${GCAL_ID}"
        )
        state = await (await c.client.get("/api/store", headers=c.headers(ALICE))).json()
        assert _item(state, "connector", "gcal")["copies"] == ["gcal-work"]
        installed = await (
            await c.client.get("/api/store/installed", headers=c.headers(ALICE))
        ).json()
        assert installed["connector:gcal-work"]["copy_of"] == "gcal"
        again = await _install(c, url, "connector", "gcal", name="gcal-work")
        assert again.status == 409


async def test_a_code_connector_copy_maps_its_declared_variables(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        response = await _install(c, url, "connector", "hello", name="hello-2", trust_code=True)
        assert response.status == 200, await response.text()
        config = c.agent_world.connector_store.get("hello-2").config
        assert config["variables"] == {"HELLO_TOKEN": "HELLO_2_HELLO_TOKEN"}


async def test_only_a_connector_installs_under_another_name(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        response = await _install(c, url, "agent", "cal", name="cal-2")
        assert response.status == 400
        assert (await _install(c, url, "connector", "gcal", name="Bad Name")).status == 400


async def test_an_update_by_the_id_here_reaches_a_copy_and_keeps_who_has_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        h = c.headers(ALICE, write=True)
        assert (await _install(c, url, "connector", "gcal")).status == 200
        assert (await _install(c, url, "connector", "gcal", name="gcal-work")).status == 200
        store = c.agent_world.connector_store
        copy = store.get("gcal-work")
        await store.put(copy.model_copy(update={"available_to": ["everyone"], "enabled": False}))

        commit_change(tmp_path / "source", "connectors/gcal.yaml", "Google Calendar", "Calendar 2")
        await c.client.post("/api/store/refresh", headers=h)
        body = {"kind": "connector", "id": "gcal-work"}
        response = await c.client.post("/api/store/update", json=body, headers=h)
        assert response.status == 200, await response.text()

        copy = store.get("gcal-work")
        assert copy.description == "Calendar 2"
        assert copy.config["headers"]["X-Client"] == "${GCAL_WORK_GCAL_ID}"
        assert (copy.available_to, copy.enabled) == (["everyone"], False)
        assert store.get("gcal").description == "Google Calendar"  # only the one asked for

        made_here = {"kind": "connector", "id": "mine"}
        await store.put(Connector(id="mine", config={"command": "x"}))
        assert (await c.client.post("/api/store/update", json=made_here, headers=h)).status == 404
        refused = await c.client.post(
            "/api/store/update", json=body, headers=c.headers(BOB, write=True)
        )
        assert refused.status == 403


async def test_an_agent_updated_from_its_page_keeps_who_has_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        h = c.headers(ALICE, write=True)
        assert (await _install(c, url, "agent", "cal")).status == 200
        agents = c.agent_world.agents
        mine = agents.get("cal").model_copy(update={"enabled": False, "available_to": ["everyone"]})
        await agents.save(mine)

        commit_change(tmp_path / "source", "agents/cal.md", "'1.0.0'", "'1.2.0'")
        commit_change(tmp_path / "source", "agents/cal.md", "manage the", "keep the")
        await c.client.post("/api/store/refresh", headers=h)
        body = {"kind": "agent", "id": "cal"}
        response = await c.client.post("/api/store/update", json=body, headers=h)
        assert response.status == 200, await response.text()
        assert (await response.json())["version"] == "1.2.0"
        cal = agents.get("cal")
        assert "keep the calendar" in cal.prompt
        assert (cal.enabled, cal.available_to) == (False, ["everyone"])


async def test_each_installed_item_tells_its_source_and_version(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        assert (await _install(c, url, "trigger", "brief")).status == 200
        rows = await (await c.client.get("/api/store/installed", headers=c.headers(ALICE))).json()
        assert rows["agent:cal"]["source_name"] == "Test templates"
        assert rows["agent:cal"]["version"] == "1.0.0"
        [trigger] = c.triggers.all()
        row = rows[f"trigger:{trigger.id}"]
        assert (row["copy_of"], row["source"], row["latest"]) == ("brief", url, None)


async def test_an_item_made_here_that_a_source_offers_too_can_be_linked(tmp_path) -> None:
    async with Console(tmp_path) as c:
        url = await _with_source(c, tmp_path)
        await c.agent_world.agents.save(Agent(id="cal", description="Mine", prompt="My own."))
        rows = await (await c.client.get("/api/store/installed", headers=c.headers(ALICE))).json()
        row = rows["agent:cal"]
        assert (row["linked"], row["version"], row["offered"], row["source"]) == (
            False,
            None,
            "1.0.0",
            url,
        )

        body = {"source": url, "kind": "agent", "id": "cal"}
        link = await c.client.post(
            "/api/store/link", json=body, headers=c.headers(ALICE, write=True)
        )
        assert link.status == 200, await link.text()
        assert c.agent_world.agents.get("cal").prompt == "My own."
        rows = await (await c.client.get("/api/store/installed", headers=c.headers(ALICE))).json()
        assert (rows["agent:cal"]["linked"], rows["agent:cal"]["version"]) == (
            True,
            "1.0.0",
        )

        again = await c.client.post(
            "/api/store/link", json=body, headers=c.headers(ALICE, write=True)
        )
        assert again.status == 409
        missing = {**body, "id": "nope"}
        none = await c.client.post(
            "/api/store/link", json=missing, headers=c.headers(ALICE, write=True)
        )
        assert none.status == 404
        assert (
            await c.client.post("/api/store/link", json=body, headers=c.headers(BOB, write=True))
        ).status == 403
