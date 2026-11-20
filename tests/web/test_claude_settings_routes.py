import yaml

from tests.web.console import ALICE, BOB, Console


async def test_the_sign_in_starts_as_what_is_running(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-from-env")
    async with Console(tmp_path) as c:
        state = await (await c.client.get("/api/settings/claude", headers=c.headers(ALICE))).json()
        assert state == {
            "auth": "subscription",
            "running_auth": "subscription",
            "credentials": {
                "subscription": {"variable": "CLAUDE_CODE_OAUTH_TOKEN", "source": None},
                "api_key": {"variable": "ANTHROPIC_API_KEY", "source": "environment"},
            },
        }


async def test_switching_to_an_api_key_writes_aios_yaml_and_a_secret(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/claude",
            json={"auth": "api_key", "value": "  sk-ant-api-123\n"},
            headers=c.headers(ALICE, write=True),
        )
        state = await response.json()
        assert response.status == 200
        assert state["auth"] == "api_key" and state["running_auth"] == "subscription"
        assert state["credentials"]["api_key"]["source"] == "variable"
        assert "sk-ant" not in str(state)
        assert yaml.safe_load(c.config_file.read_text()) == {
            "channels": ["web"],
            "agent": {"auth": "api_key"},
        }
        stored = c.variables.get("ANTHROPIC_API_KEY")
        assert stored is not None and stored.secret and stored.value != "sk-ant-api-123"
        assert c.variable_resolver.value_of("ANTHROPIC_API_KEY") == "sk-ant-api-123"


async def test_without_a_value_the_stored_credential_is_kept(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        await c.client.put(
            "/api/settings/claude", json={"auth": "subscription", "value": "tok"}, headers=h
        )
        before = c.config_file.read_text()
        await c.client.put("/api/settings/claude", json={"auth": "subscription"}, headers=h)
        assert c.variable_resolver.value_of("CLAUDE_CODE_OAUTH_TOKEN") == "tok"
        assert c.config_file.read_text() == before == "channels: [web]\n"


async def test_the_sign_in_is_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/claude", json={"auth": "api_key"}, headers=c.headers(BOB, write=True)
        )
        assert response.status == 403
        assert c.config_file.read_text() == "channels: [web]\n"


async def test_a_check_tries_the_pasted_value_without_saving_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        good = await c.client.post(
            "/api/settings/claude/check",
            json={"auth": "api_key", "value": " sk-ant-good "},
            headers=h,
        )
        bad = await c.client.post(
            "/api/settings/claude/check", json={"auth": "subscription"}, headers=h
        )
        assert (await good.json())["ok"] is True
        assert await bad.json() == {
            "ok": False,
            "error": "the token or key was refused",
            "model": None,
            "seconds": 0,
        }
        assert c.sign_in_check.asked == [("api_key", "sk-ant-good"), ("subscription", None)]
        assert c.variables.get("ANTHROPIC_API_KEY") is None
        assert c.config_file.read_text() == "channels: [web]\n"


async def test_a_check_is_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.post(
            "/api/settings/claude/check",
            json={"auth": "api_key"},
            headers=c.headers(BOB, write=True),
        )
        assert response.status == 403
        assert c.sign_in_check.asked == []
