from tests.web.console import ALICE, BOB, Console


async def test_agents_and_connectors_are_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        for path in ("/api/agents", "/api/connectors"):
            assert (await c.client.get(path, headers=c.headers(BOB))).status == 403
            assert (await c.client.get(path, headers=c.headers(ALICE))).status == 200


async def test_the_list_has_agents_skills_and_connectors(tmp_path) -> None:
    async with Console(tmp_path) as c:
        data = await (await c.client.get("/api/agents", headers=c.headers(ALICE))).json()
        assert [a["name"] for a in data["agents"]] == ["orchestrator", "calendar", "messenger"]
        [skill] = data["skills"]
        assert skill["name"] == "message-style" and skill["agents"] == ["messenger"]
        assert skill["description"] == "Voice." and skill["content"] == "Write as the user.\n"
        assert data["connectors"][0]["name"] == "aios"


async def test_an_agent_is_edited_field_by_field(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        r = await c.client.put(
            "/api/agents/calendar", json={"builtin_tools": ["WebSearch"]}, headers=h
        )
        assert r.status == 200
        calendar = c.agent_world.agents.get("calendar")
        assert calendar is not None and calendar.builtin_tools == ["WebSearch"]
        assert calendar.prompt == "You manage the calendar.\n"  # left out, so kept
        bad = await c.client.put(
            "/api/agents/calendar", json={"builtin_tools": ["Bash"]}, headers=h
        )
        assert bad.status == 400
        fixed = await c.client.put("/api/agents/messenger", json={"enabled": False}, headers=h)
        assert fixed.status == 400
        assert (await c.client.delete("/api/agents/messenger", headers=h)).status == 409


async def test_a_custom_agent_is_created_once(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"name": "travel", "description": "Trips", "prompt": "Plan trips."}
        assert (await c.client.post("/api/agents", json=body, headers=h)).status == 201
        assert (await c.client.post("/api/agents", json=body, headers=h)).status == 409
        assert (await c.client.delete("/api/agents/travel", headers=h)).status == 200
        assert c.agent_world.agents.get("travel") is None


async def test_connectors_are_created_changed_and_deleted(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"name": "gcal", "config": {"command": "npx"}}
        assert (await c.client.post("/api/connectors", json=body, headers=h)).status == 201
        assert (await c.client.post("/api/connectors", json=body, headers=h)).status == 409
        builtin = {"name": "aios", "config": {"command": "x"}}
        assert (await c.client.post("/api/connectors", json=builtin, headers=h)).status == 400
        r = await c.client.put(
            "/api/connectors/gcal", json={"config": {"command": "npx"}, "enabled": False}, headers=h
        )
        assert r.status == 200 and not c.agent_world.connectors.is_enabled("gcal")
        data = await (await c.client.get("/api/connectors", headers=h)).json()
        gcal = next(row for row in data["connectors"] if row["id"] == "gcal")
        assert gcal["used_by"] == ["calendar"]
        assert (await c.client.put("/api/connectors/aios", json=body, headers=h)).status == 409
        assert (await c.client.delete("/api/connectors/gcal", headers=h)).status == 200


async def test_a_web_conversation_can_go_straight_to_an_agent(tmp_path) -> None:
    async with Console(tmp_path) as c:
        listed = await (await c.client.get("/api/chat/agents", headers=c.headers(BOB))).json()
        assert [a["name"] for a in listed["agents"]] == ["orchestrator", "calendar", "messenger"]
        h = c.headers(BOB, write=True)
        r = await c.client.post(
            "/api/conversations", json={"text": "hi", "agent": "calendar"}, headers=h
        )
        assert r.status == 201
        conversation = c.world.conversations.get((await r.json())["id"])
        assert conversation is not None and conversation.agent == "calendar"
        bad = await c.client.post(
            "/api/conversations", json={"text": "hi", "agent": "nobody"}, headers=h
        )
        assert bad.status == 400
        usual = await c.client.post(
            "/api/conversations", json={"text": "hi", "agent": "orchestrator"}, headers=h
        )
        assert c.world.conversations.get((await usual.json())["id"]).agent is None  # type: ignore[union-attr]


async def test_a_schedule_may_name_an_existing_agent(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"name": "b", "prompt": "p", "cron": ["0 7 * * *"], "user_id": "alice"}
        ok = await c.client.post("/api/schedules", json={**body, "agent": "calendar"}, headers=h)
        assert ok.status == 201
        assert c.schedules.get((await ok.json())["id"]).agent == "calendar"  # type: ignore[union-attr]
        bad = await c.client.post("/api/schedules", json={**body, "agent": "nobody"}, headers=h)
        assert bad.status == 400


async def test_a_skill_is_edited(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"description": "Voice.", "content": "Write short.\n"}
        assert (await c.client.put("/api/skills/message-style", json=body, headers=h)).status == 200
        assert c.skills.get("message-style").content == "Write short.\n"  # type: ignore[union-attr]


async def test_a_skill_is_created_granted_and_deleted_with_its_grants(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"name": "travel-style", "description": "Trips.", "content": "Plan by train.\n"}
        assert (await c.client.post("/api/skills", json=body, headers=h)).status == 201
        assert (await c.client.post("/api/skills", json=body, headers=h)).status == 409
        for agent in ("calendar", "messenger"):
            skills = [*c.agent_world.agents.get(agent).skills, "travel-style"]  # type: ignore[union-attr]
            await c.client.put(f"/api/agents/{agent}", json={"skills": skills}, headers=h)
        assert "travel-style" in c.agent_world.agents.get("calendar").skills  # type: ignore[union-attr]
        assert (await c.client.delete("/api/skills/travel-style", headers=h)).status == 200
        assert c.skills.get("travel-style") is None
        assert "travel-style" not in c.agent_world.agents.get("calendar").skills  # type: ignore[union-attr]
        assert c.agent_world.agents.get("messenger").skills == ["message-style"]  # type: ignore[union-attr]


async def test_the_sign_in_callback_needs_no_csrf_header_but_a_known_state(tmp_path) -> None:
    async with Console(tmp_path) as c:
        r = await c.client.post(
            "/api/oauth/callback",
            data={"state": "unknown", "code": "x"},
            headers=c.headers(ALICE),
            allow_redirects=False,
        )
        assert r.status == 302
        assert (
            r.headers["Location"].startswith("/?sign_in_error=")
            and "#/connectors" in r.headers["Location"]
        )
        denied = await c.client.get(
            "/api/oauth/callback?error=access_denied",
            headers=c.headers(ALICE),
            allow_redirects=False,
        )
        assert denied.headers["Location"] == "/?sign_in_error=access_denied#/connectors"
        other = await c.client.post("/api/connectors/gcal/sign-in", headers=c.headers(ALICE))
        assert other.status == 403  # everywhere else the header is still required
        assert (await c.client.get("/api/oauth/callback", headers=c.headers(BOB))).status == 403


async def test_a_secret_never_comes_back_out_of_the_api(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"name": "HOMEY_TOKEN", "value": "s3cret", "secret": True}
        assert (await c.client.post("/api/variables", json=body, headers=h)).status == 201
        plain = {"name": "REGION", "value": "eu"}
        assert (await c.client.post("/api/variables", json=plain, headers=h)).status == 201
        listed = await (await c.client.get("/api/variables", headers=h)).text()
        assert "s3cret" not in listed and '"value": "eu"' in listed
        assert (await c.client.get("/api/variables", headers=c.headers(BOB))).status == 403
        edit = {"secret": True, "description": "Homey"}
        assert (
            await c.client.put("/api/variables/HOMEY_TOKEN", json=edit, headers=h)
        ).status == 200
        assert (await c.client.delete("/api/variables/REGION", headers=h)).status == 200


async def test_a_connector_can_be_started_to_see_whether_it_comes_up(tmp_path) -> None:
    from aios.connectors.probe_result import ProbeResult

    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        await c.client.post(
            "/api/connectors", json={"name": "gmail", "config": {"command": "npx"}}, headers=h
        )
        c.probe.results["gmail"] = ProbeResult(status="failed", error="Premature close")
        r = await c.client.post("/api/connectors/gmail/start", headers=h)
        assert r.status == 200 and (await r.json())["error"] == "Premature close"
        listed = await (await c.client.get("/api/connectors", headers=h)).json()
        gmail = next(row for row in listed["connectors"] if row["id"] == "gmail")
        assert gmail["status"] == "failed" and gmail["error"] == "Premature close"
        assert (await c.client.post("/api/connectors/nope/start", headers=h)).status == 404
        assert (
            await c.client.post("/api/connectors/gmail/start", headers=c.headers(BOB, write=True))
        ).status == 403
