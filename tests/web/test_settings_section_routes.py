import yaml

from tests.web.console import ALICE, BOB, Console

YAML = """\
channels: [web]
approval:
  always:          # asked every time
    - mcp__gcal__update-event
agent:
  auth: api_key
"""


async def test_sections_come_with_their_schema_and_what_is_set(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(YAML)
        data = await (await c.client.get("/api/settings/sections", headers=c.headers(ALICE))).json()
        sections = data["sections"]
        assert set(sections) == {
            "timezone",
            "scheduler",
            "agent",
            "approval",
            "collection_access",
        }
        assert data["collections"] == {"memories": "write"}
        assert sections["approval"]["value"] == {"always": ["mcp__gcal__update-event"]}
        assert sections["scheduler"]["value"] is None
        assert sections["timezone"]["schema"]["default"] == "Europe/Zurich"
        assert "$defs" in sections["agent"]["schema"]


async def test_a_section_save_keeps_the_rest_and_its_comments(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(YAML)
        value = {"always": ["mcp__gcal__update-event"], "deny": ["mcp__gmail__send_email"]}
        response = await c.client.put(
            "/api/settings/sections/approval",
            json={"value": value},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        text = c.config_file.read_text()
        assert "# asked every time" in text
        assert yaml.safe_load(text) == {
            "channels": ["web"],
            "approval": value,
            "agent": {"auth": "api_key"},
        }


async def test_a_wrong_value_is_refused_with_a_readable_reason(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(YAML)
        h = c.headers(ALICE, write=True)
        bash = await c.client.put(
            "/api/settings/sections/agent",
            json={"value": {"auth": "api_key", "builtin_tools": ["Bash"]}},
            headers=h,
        )
        zone = await c.client.put(
            "/api/settings/sections/timezone", json={"value": "Mars/Base"}, headers=h
        )
        assert bash.status == 400 and "Bash is never given" in await bash.text()
        assert zone.status == 400 and "unknown timezone" in await zone.text()
        assert c.config_file.read_text() == YAML


async def test_web_and_other_sections_stay_on_the_yaml_tab(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/sections/web",
            json={"value": {"enabled": False}},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 404


async def test_sections_are_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/sections/timezone",
            json={"value": "UTC"},
            headers=c.headers(BOB, write=True),
        )
        assert response.status == 403


async def test_agent_access_can_change_only_where_it_is_not_fixed(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        ok = await c.client.put(
            "/api/settings/sections/collection_access",
            json={"value": {"memories": "read"}},
            headers=h,
        )
        fixed = await c.client.put(
            "/api/settings/sections/collection_access",
            json={"value": {"agents": "write"}},
            headers=h,
        )
        assert ok.status == 200 and fixed.status == 400
        assert "fixed for agents" in await fixed.text()
        assert yaml.safe_load(c.config_file.read_text())["collection_access"] == {
            "memories": "read"
        }
