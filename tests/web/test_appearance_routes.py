from tests.web.console import ALICE, BOB, Console


async def test_nothing_is_chosen_until_someone_chooses(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.get("/api/me/appearance", headers=c.headers(ALICE))
        assert response.status == 200
        assert await response.json() is None


async def test_a_choice_follows_the_user_and_is_theirs_alone(tmp_path) -> None:
    async with Console(tmp_path) as c:
        chosen = {"mode": "dark", "theme": "teal"}
        saved = await c.client.put(
            "/api/me/appearance", json=chosen, headers=c.headers(ALICE, write=True)
        )
        assert saved.status == 200
        assert await saved.json() == chosen
        again = await c.client.get("/api/me/appearance", headers=c.headers(ALICE))
        assert await again.json() == chosen
        bobs = await c.client.get("/api/me/appearance", headers=c.headers(BOB))
        assert await bobs.json() is None


async def test_only_known_modes_and_plain_theme_names_are_kept(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        for body in (
            {"mode": "sepia", "theme": "teal"},
            {"mode": "dark", "theme": "Teal; color:red"},
            {"mode": "dark"},
        ):
            response = await c.client.put("/api/me/appearance", json=body, headers=h)
            assert response.status == 400, body


async def test_saving_needs_a_signed_in_caller_and_the_csrf_header(tmp_path) -> None:
    async with Console(tmp_path) as c:
        body = {"mode": "light", "theme": "rose"}
        anonymous = await c.client.put("/api/me/appearance", json=body, headers={"X-Aios": "1"})
        assert anonymous.status in (401, 403)
        no_header = await c.client.put("/api/me/appearance", json=body, headers=c.headers(ALICE))
        assert no_header.status == 403
