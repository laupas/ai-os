import gzip

from tests.web.console import ALICE, BOB, Console


async def test_an_administrator_downloads_a_sealed_backup(tmp_path) -> None:
    async with Console(tmp_path) as c:
        (tmp_path / "data" / "users").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data" / "users" / "alice.json").write_text('{"name": "Alice Example"}')
        response = await c.client.post("/api/backup", headers=c.headers(ALICE, write=True))
        assert response.status == 200
        assert response.headers["Content-Type"] == "application/octet-stream"
        disposition = response.headers["Content-Disposition"]
        assert disposition.startswith('attachment; filename="aios-backup-')
        assert response.headers["Cache-Control"] == "no-store"
        blob = await response.read()
        assert b"Alice Example" not in blob
        assert b"data/users/alice.json" in gzip.decompress(c.backup_cipher.open(blob))


async def test_only_administrators_with_the_csrf_header_get_one(tmp_path) -> None:
    async with Console(tmp_path) as c:
        bob = await c.client.post("/api/backup", headers=c.headers(BOB, write=True))
        assert bob.status == 403
        no_header = await c.client.post("/api/backup", headers=c.headers(ALICE))
        assert no_header.status == 403
        assert (await c.client.get("/api/backup", headers=c.headers(ALICE))).status in (404, 405)


async def _backup(c) -> bytes:  # type: ignore[no-untyped-def]
    (c.tmp_path / "data" / "users").mkdir(parents=True, exist_ok=True)
    (c.tmp_path / "data" / "users" / "alice.json").write_text('{"name": "Alice Example"}')
    response = await c.client.post("/api/backup", headers=c.headers(ALICE, write=True))
    return await response.read()


async def test_a_restore_is_checked_then_confirmed_or_discarded(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        blob = await _backup(c)
        status = await (await c.client.get("/api/backup/restore", headers=h)).json()
        assert status == {"pending": None, "confirmed": False, "failure": None, "last": None}

        uploaded = await c.client.post(
            "/api/backup/restore",
            data=blob,
            headers={**h, "Content-Type": "application/octet-stream"},
        )
        assert uploaded.status == 200
        contents = await uploaded.json()
        assert contents["key_fingerprint"] == c.secrets_box.fingerprint()
        assert contents["folders"]["users"] == 1 and contents["files"] >= 1

        assert (await c.client.post("/api/backup/restore/confirm", headers=h)).status == 200
        status = await (await c.client.get("/api/backup/restore", headers=h)).json()
        assert status["confirmed"] and status["pending"]["files"] == contents["files"]

        assert (await c.client.delete("/api/backup/restore", headers=h)).status == 200
        status = await (await c.client.get("/api/backup/restore", headers=h)).json()
        assert status["pending"] is None and not status["confirmed"]
        assert (await c.client.post("/api/backup/restore/confirm", headers=h)).status == 404


async def test_what_cannot_be_restored_is_refused_at_upload(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = {**c.headers(ALICE, write=True), "Content-Type": "application/octet-stream"}
        garbage = await c.client.post("/api/backup/restore", data=b"PK\x03\x04", headers=h)
        assert garbage.status == 400 and "not a backup of ai-os" in await garbage.text()
        assert not (tmp_path / "data" / ".restore" / "pending.json").exists()


async def test_only_administrators_restore(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(BOB, write=True)
        assert (await c.client.get("/api/backup/restore", headers=h)).status == 403
        assert (await c.client.post("/api/backup/restore", data=b"x", headers=h)).status == 403
        assert (await c.client.post("/api/backup/restore/confirm", headers=h)).status == 403
        assert (await c.client.delete("/api/backup/restore", headers=h)).status == 403
