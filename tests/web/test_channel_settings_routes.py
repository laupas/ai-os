import yaml

from tests.web.console import ALICE, BOB, Console

OLD = "channels: [web]\nsenders: [signal]          # a comment\n"


async def read(c: Console) -> dict:
    data = await (await c.client.get("/api/settings/channels", headers=c.headers(ALICE))).json()
    return {ch["name"]: ch for ch in data["channels"]}


async def test_every_channel_is_listed_with_what_it_needs_and_no_secret(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-from-env")
    async with Console(tmp_path) as c:
        c.config_file.write_text(OLD)
        channels = await read(c)
        assert list(channels)[:4] == ["slack", "web", "signal", "mail"]
        slack, signal = channels["slack"], channels["signal"]
        assert slack["capabilities"] == ["chat"] and not slack["enabled"]
        assert signal["capabilities"] == ["send"] and signal["enabled"]
        assert channels["web"]["running"] and channels["web"]["fields"] == []
        bot = slack["fields"][0]
        assert bot["variable"] == "SLACK_BOT_TOKEN" and bot["source"] == "environment"
        assert bot["value"] is None and "xoxb-from-env" not in str(channels)
        url = signal["fields"][0]
        assert url["value"] == "http://signal-api:8080" and url["source"] == "default"
        assert slack["checkable"] and not channels["web"]["checkable"]


async def test_values_become_variables_and_on_rewrites_the_older_lists(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(OLD)
        response = await c.client.put(
            "/api/settings/channels/fake",
            json={"enabled": True, "values": {"FAKE_TOKEN": " tok ", "FAKE_URL": "http://y"}},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        assert yaml.safe_load(c.config_file.read_text()) == {
            "channels": {
                "web": {"enabled": True},
                "signal": {"enabled": True},
                "fake": {"enabled": True},
            }
        }
        token, url = c.variables.get("FAKE_TOKEN"), c.variables.get("FAKE_URL")
        assert token is not None and token.secret and token.value != "tok"
        assert url is not None and not url.secret and url.value == "http://y"
        assert c.variable_resolver.value_of("FAKE_TOKEN") == "tok"


async def test_a_chat_channel_without_its_values_is_not_switched_on(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/channels/slack",
            json={"enabled": True},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 400 and "Bot token" in await response.text()
        assert c.config_file.read_text() == "channels: [web]\n"


async def test_the_last_chat_channel_stays_on(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        last = await c.client.put("/api/settings/channels/web", json={"enabled": False}, headers=h)
        assert last.status == 409
        await c.client.put(
            "/api/settings/channels/fake",
            json={"enabled": True, "values": {"FAKE_TOKEN": "tok"}},
            headers=h,
        )
        now = await c.client.put("/api/settings/channels/web", json={"enabled": False}, headers=h)
        assert now.status == 200
        assert yaml.safe_load(c.config_file.read_text())["channels"]["web"] == {"enabled": False}


async def test_a_check_tries_typed_values_without_saving_them(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        good = await c.client.post(
            "/api/settings/channels/fake/check", json={"values": {"FAKE_TOKEN": "good"}}, headers=h
        )
        assert await good.json() == {"ok": True, "detail": "checked"}
        assert c.fake_type.checked == [{"FAKE_TOKEN": "good", "FAKE_URL": "http://x"}]
        assert c.variables.get("FAKE_TOKEN") is None
        none = await c.client.post("/api/settings/channels/web/check", json={}, headers=h)
        assert none.status == 404


async def test_unknown_values_and_non_administrators_are_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        odd = await c.client.put(
            "/api/settings/channels/fake",
            json={"values": {"OTHER": "x"}},
            headers=c.headers(ALICE, write=True),
        )
        bob = await c.client.put(
            "/api/settings/channels/fake",
            json={"enabled": True},
            headers=c.headers(BOB, write=True),
        )
        assert odd.status == 400 and bob.status == 403
