from tests.web.console import ALICE, Console


async def test_a_code_connector_is_added_with_its_agents_and_keeps_fixed_settings_off_it(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        listing = await (await c.client.get("/api/connectors", headers=h)).json()
        crypto = next(x for x in listing["library"] if x["name"] == "crypto")
        assert crypto["agents"] == ["crypto-advisor", "crypto-trader"]

        r = await c.client.post(
            "/api/connectors", json={"name": "crypto", "config": {"code": "crypto"}}, headers=h
        )
        row = await r.json()
        assert r.status == 201 and row["added_agents"] == ["crypto-advisor", "crypto-trader"]
        assert row["code"]["fixed"] == {"max_chf_per_day": 300}
        assert row["code"]["effective"]["max_chf_per_order"] == 200
        assert row["missing_variables"] == ["KRAKEN_API_KEY", "KRAKEN_API_SECRET"]

        settings = {"max_chf_per_day": 9999, "min_chf": 20}
        r = await c.client.put(
            "/api/connectors/crypto",
            json={"config": {"code": "crypto", "settings": settings}},
            headers=h,
        )
        row = await r.json()
        assert row["code"]["settings"] == {"min_chf": 20}  # the fixed one is not stored
        assert row["code"]["effective"]["max_chf_per_day"] == 300

        r = await c.client.post(
            "/api/connectors", json={"name": "x", "config": {"code": "nowhere"}}, headers=h
        )
        assert r.status == 400
