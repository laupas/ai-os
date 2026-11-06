from tests.web.console import ALICE, Console


async def test_a_code_connector_is_added_with_its_agents_and_keeps_fixed_settings_off_it(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        listing = await (await c.client.get("/api/connectors", headers=h)).json()
        (offer,) = listing["library"]
        assert offer["name"] == "hello-world" and offer["agents"] == ["hello-greeter"]

        r = await c.client.post(
            "/api/connectors",
            json={"name": "hello-world", "config": {"code": "hello-world"}},
            headers=h,
        )
        row = await r.json()
        assert r.status == 201 and row["added_agents"] == ["hello-greeter"]
        assert row["code"]["fixed"] == {"max_shout_length": 3}
        assert row["code"]["effective"] == {"greeting": "Hello", "max_shout_length": 3}
        assert row["missing_variables"] == ["HELLO_TOKEN"]

        r = await c.client.put(
            "/api/connectors/hello-world",
            json={
                "config": {
                    "code": "hello-world",
                    "settings": {"max_shout_length": 99, "greeting": "Hi"},
                }
            },
            headers=h,
        )
        row = await r.json()
        assert row["code"]["settings"] == {"greeting": "Hi"}  # the fixed one is not stored
        assert row["code"]["effective"]["max_shout_length"] == 3

        r = await c.client.post(
            "/api/connectors", json={"name": "x", "config": {"code": "nowhere"}}, headers=h
        )
        assert r.status == 400
