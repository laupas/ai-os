from tests.web.console import ALICE, BOB, Console


async def _switch(c: Console, on: bool) -> None:
    body = {"value": {"enabled": True} if on else None}
    response = await c.client.put(
        "/api/settings/sections/api_docs", json=body, headers=c.headers(ALICE, write=True)
    )
    assert response.status == 200


async def test_the_docs_are_off_until_switched_on(tmp_path) -> None:
    async with Console(tmp_path) as c:
        assert (await c.client.get("/api/docs", headers=c.headers(ALICE))).status == 404
        assert (await c.client.get("/api/openapi.json", headers=c.headers(ALICE))).status == 404
        await _switch(c, True)
        page = await c.client.get("/api/docs", headers=c.headers(ALICE))
        assert page.status == 200
        assert "swagger-ui" in await page.text()
        await _switch(c, False)
        assert (await c.client.get("/api/docs", headers=c.headers(ALICE))).status == 404


async def test_only_administrators_and_signed_in_ones_see_them(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _switch(c, True)
        assert (await c.client.get("/api/openapi.json")).status == 403
        assert (await c.client.get("/api/openapi.json", headers=c.headers(BOB))).status == 403


async def test_the_description_names_every_route_with_its_body_and_permission(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await _switch(c, True)
        spec = await (await c.client.get("/api/openapi.json", headers=c.headers(ALICE))).json()
        assert spec["openapi"] == "3.1.0"
        routes = {(m.upper(), path) for path, item in spec["paths"].items() for m in item}
        served = {
            (r.method, r.resource.canonical)
            for r in c.client.app.router.routes()
            if r.method != "HEAD" and r.resource.canonical.startswith(("/api/", "/hooks/"))
        }
        assert served <= routes
        install = spec["paths"]["/api/store/install"]["post"]
        assert install["tags"] == ["Store"]
        ref = install["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/StoreInstallRequest"
        assert "id" in spec["components"]["schemas"]["StoreInstallRequest"]["properties"]
        assert "administer" in install["description"]
        hook = spec["paths"]["/hooks/triggers/{id}"]["post"]
        assert hook["security"] == [{"hookToken": []}]
        assert spec["paths"]["/api/openapi.json"]["get"]["summary"] == (
            "The OpenAPI description of this API."
        )
