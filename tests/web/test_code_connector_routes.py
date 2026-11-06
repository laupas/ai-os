from tests.web.console import ALICE, Console


async def test_a_code_connector_is_added_with_its_agents_and_keeps_fixed_settings_off_it(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        listing = await (await c.client.get("/api/connectors", headers=h)).json()
        (offer,) = listing["library"]
        assert offer["name"] == "echo" and offer["agents"] == ["echo-agent"]

        r = await c.client.post(
            "/api/connectors", json={"name": "echo", "config": {"code": "echo"}}, headers=h
        )
        row = await r.json()
        assert r.status == 201 and row["added_agents"] == ["echo-agent"]
        assert row["code"]["fixed"] == {"max_length": 3}
        assert row["code"]["effective"] == {"greeting": "hello", "max_length": 3}
        assert row["missing_variables"] == ["ECHO_TOKEN"]

        r = await c.client.put(
            "/api/connectors/echo",
            json={"config": {"code": "echo", "settings": {"max_length": 99, "greeting": "hi"}}},
            headers=h,
        )
        row = await r.json()
        assert row["code"]["settings"] == {"greeting": "hi"}  # the fixed one is not stored
        assert row["code"]["effective"]["max_length"] == 3

        r = await c.client.post(
            "/api/connectors", json={"name": "x", "config": {"code": "nowhere"}}, headers=h
        )
        assert r.status == 400
