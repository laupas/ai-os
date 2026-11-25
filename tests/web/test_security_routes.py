from cryptography.fernet import Fernet

from aios.variables.secret_box import SecretBox
from tests.web.console import ALICE, BOB, Console


async def test_the_status_names_the_key_by_its_fingerprint_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        await c.variables.save("API_TOKEN", "s3cret", True, False, "", "Alice")
        await c.variables.save("REGION", "eu", False, False, "", "Alice")
        response = await c.client.get("/api/security", headers=c.headers(ALICE))
        assert response.status == 200
        status = await response.json()
        assert status["origin"] == "setting" and not status["legacy_file"]
        assert status["fingerprint"] == c.secrets_box.fingerprint()
        assert (status["total"], status["on_previous"], status["unreadable"]) == (1, 0, [])
        assert "a test key" not in await response.text()


async def test_only_administrators_see_or_get_keys(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(BOB, write=True)
        assert (await c.client.get("/api/security", headers=h)).status == 403
        assert (await c.client.post("/api/security/keys", headers=h)).status == 403
        assert (await c.client.post("/api/security/data-dir-key", headers=h)).status == 403


async def test_a_new_key_is_handed_out_and_never_kept(tmp_path) -> None:
    async with Console(tmp_path) as c:
        before = c.secrets_box.fingerprint()
        response = await c.client.post("/api/security/keys", headers=c.headers(ALICE, write=True))
        body = await response.json()
        Fernet(body["key"])  # a usable key
        assert body["fingerprint"] == SecretBox.fingerprint_of(body["key"]) != before
        status = await (await c.client.get("/api/security", headers=c.headers(ALICE))).json()
        assert status["fingerprint"] == before
        assert body["key"] not in str(list(tmp_path.rglob("*")))
        refused = await c.client.post("/api/security/keys", headers=c.headers(ALICE))
        assert refused.status == 403  # without the CSRF header


async def test_an_older_key_file_can_be_read_out_to_move_it(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        assert (await c.client.post("/api/security/data-dir-key", headers=h)).status == 404
        legacy = SecretBox.new_key()
        (tmp_path / "secrets.key").write_text(legacy)
        body = await (await c.client.post("/api/security/data-dir-key", headers=h)).json()
        assert body == {"key": legacy, "fingerprint": SecretBox.fingerprint_of(legacy)}
