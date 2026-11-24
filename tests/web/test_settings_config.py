import json

from tests.web.console import ALICE, Console


def text(data: dict) -> dict:
    return {"text": json.dumps(data)}


async def test_a_key_from_the_reference_goes_into_the_text_keeping_its_comments(
    tmp_path,
) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        settings = await (await c.client.get("/api/settings", headers=h)).json()
        assert "AgentConfig" in settings["config_schema"]["$defs"]
        text = "# keep me\nchannels: [web]\n"
        r = await c.client.post(
            "/api/settings/config-insert",
            json={"text": text, "path": ["agent", "auth"], "value": "subscription"},
            headers=h,
        )
        inserted = (await r.json())["text"]
        assert inserted.startswith("# keep me\n") and "agent:\n  auth: subscription" in inserted
        assert c.config_file.read_text() == "channels: [web]\n"  # nothing saved
