import yaml

from tests.web.console import ALICE, BOB, Console

OLDER = """\
channels: [web]
# The web console.
web:
  enabled: true
  access_team_domain: example.cloudflareaccess.com
  access_aud: abc
"""
# How the test console tells who is asking, as a trusted header from localhost.
SAME = {"mode": "header", "header": "X-Test-Email", "trusted_proxies": ["127.0.0.1/32", "::1/128"]}


async def test_the_older_keys_are_shown_as_cloudflare(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(OLDER)
        data = await (await c.client.get("/api/settings/web-auth", headers=c.headers(ALICE))).json()
        assert data["older_form"] is True and data["you"] == ALICE
        auth = data["auth"]
        assert (auth["mode"], auth["team_domain"], auth["audience"]) == (
            "cloudflare",
            "example.cloudflareaccess.com",
            "abc",
        )


async def test_a_login_that_recognises_you_is_saved_in_the_new_form(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(OLDER)
        h = c.headers(ALICE, write=True)
        check = await (
            await c.client.post("/api/settings/web-auth/check", json={"auth": SAME}, headers=h)
        ).json()
        assert check["ok"] and check["email"] == ALICE
        response = await c.client.put(
            "/api/settings/web-auth",
            json={"auth": SAME, "public_url": "https://ai-os.example.com/"},
            headers=h,
        )
        assert response.status == 200
        text = c.config_file.read_text()
        assert "# The web console." in text
        assert yaml.safe_load(text)["web"] == {
            "enabled": True,
            "auth": SAME,
            "public_url": "https://ai-os.example.com",
        }


async def test_a_login_that_would_lock_you_out_is_not_saved(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(OLDER)
        h = c.headers(ALICE, write=True)
        wrong = {**SAME, "header": "X-Somebody"}
        cloudflare = {
            "mode": "cloudflare",
            "team_domain": "x.cloudflareaccess.com",
            "audience": "a",
        }
        for auth in (wrong, cloudflare):
            response = await c.client.put("/api/settings/web-auth", json={"auth": auth}, headers=h)
            assert response.status == 409 and "locked out" in await response.text()
        dev = await c.client.put(
            "/api/settings/web-auth",
            json={"auth": {"mode": "dev", "dev_email": ALICE}},
            headers=h,
        )
        assert dev.status == 400
        assert c.config_file.read_text() == OLDER


async def test_the_login_is_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/web-auth", json={"auth": SAME}, headers=c.headers(BOB, write=True)
        )
        assert response.status == 403
