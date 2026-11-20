from tests.web.console import ALICE, Console


async def test_a_code_connector_is_added_with_its_agents_and_shows_its_locks(tmp_path) -> None:
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
        assert row["code"]["locked"] == ["max_shout_length"]
        assert row["code"]["effective"] == {"greeting": "Hello", "max_shout_length": 20}
        assert row["missing_variables"] == []  # HELLO_TOKEN is not required
        (field,) = row["code"]["variables"]
        assert field["variable"] == "HELLO_TOKEN" and field["source"] is None

        # The console is administrators only: a locked setting is changed here.
        r = await c.client.put(
            "/api/connectors/hello-world",
            json={
                "config": {
                    "code": "hello-world",
                    "settings": {"max_shout_length": 5, "greeting": "Hi"},
                }
            },
            headers=h,
        )
        row = await r.json()
        assert row["code"]["settings"] == {"max_shout_length": 5, "greeting": "Hi"}

        r = await c.client.post(
            "/api/connectors", json={"name": "x", "config": {"code": "nowhere"}}, headers=h
        )
        assert r.status == 400


async def test_a_declared_variable_is_saved_as_a_secret_variable(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        body = {"name": "hello-world", "config": {"code": "hello-world"}}
        await c.client.post("/api/connectors", json=body, headers=h)
        r = await c.client.put(
            "/api/connectors/hello-world",
            json={"config": {"code": "hello-world"}, "variables": {"HELLO_TOKEN": "tok"}},
            headers=h,
        )
        row = await r.json()
        assert r.status == 200
        (field,) = row["code"]["variables"]
        assert field["source"] == "variable" and field["value"] is None  # never sent back
        assert c.variables.get("HELLO_TOKEN").secret  # type: ignore[union-attr]
        assert c.variable_resolver.value_of("HELLO_TOKEN") == "tok"

        r = await c.client.put(
            "/api/connectors/hello-world",
            json={"config": {"code": "hello-world"}, "variables": {"OTHER": "x"}},
            headers=h,
        )
        assert r.status == 400
