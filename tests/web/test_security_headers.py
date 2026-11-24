from tests.web.console import ALICE, Console


async def test_every_answer_carries_the_security_headers(tmp_path) -> None:
    async with Console(tmp_path) as c:
        for path in ("/", "/api/me", "/static/assets/index-abc123.js", "/api/nothing-here"):
            headers = (await c.client.get(path, headers=c.headers(ALICE))).headers
            assert "script-src 'self'" in headers["Content-Security-Policy"]
            assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
            assert headers["X-Frame-Options"] == "DENY"
            assert headers["X-Content-Type-Options"] == "nosniff"
            assert headers["Referrer-Policy"] == "same-origin"
            assert "microphone=(self)" in headers["Permissions-Policy"]


async def test_hsts_only_once_the_console_is_reached_over_https(tmp_path) -> None:
    async with Console(tmp_path) as c:
        plain = await c.client.get("/")
        assert "Strict-Transport-Security" not in plain.headers
        proxied = await c.client.get("/", headers={"X-Forwarded-Proto": "https"})
        assert proxied.headers["Strict-Transport-Security"].startswith("max-age=31536000")


async def test_the_api_docs_page_keeps_its_own_policy(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.client.put(
            "/api/settings/sections/api_docs",
            json={"value": {"enabled": True}},
            headers=c.headers(ALICE, write=True),
        )
        page = await c.client.get("/api/docs", headers=c.headers(ALICE))
        assert "https://cdn.jsdelivr.net" in page.headers["Content-Security-Policy"]
        assert page.headers["X-Frame-Options"] == "DENY"
