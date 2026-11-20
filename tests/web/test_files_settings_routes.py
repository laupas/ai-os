import yaml

from tests.web.console import ALICE, BOB, Console


async def test_folders_come_with_whether_they_exist_and_the_mounts_to_offer(tmp_path) -> None:
    async with Console(tmp_path) as c:
        c.config_file.write_text(f"files:\n  read_roots: [{c.vault}, /nowhere]\n")
        data = await (await c.client.get("/api/settings/files", headers=c.headers(ALICE))).json()
        assert data["read_roots"] == [str(c.vault), "/nowhere"]
        assert data["paths"][str(c.vault)]["exists"] is True
        assert data["paths"]["/nowhere"] == {"problem": None, "exists": False, "real": None}
        assert data["mounts"] == [str(c.vault)]  # not /, not the data dir


async def test_folders_are_saved_tidied(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/files",
            json={"read_roots": [f" {c.vault}/ ", str(c.vault)], "write_roots": []},
            headers=c.headers(ALICE, write=True),
        )
        assert response.status == 200
        assert yaml.safe_load(c.config_file.read_text()) == {
            "channels": ["web"],
            "files": {"read_roots": [str(c.vault)]},
        }
        await c.client.put("/api/settings/files", json={}, headers=c.headers(ALICE, write=True))
        assert c.config_file.read_text() == "channels: [web]\n"


async def test_a_folder_that_reaches_protected_ones_is_refused(tmp_path) -> None:
    async with Console(tmp_path) as c:
        h = c.headers(ALICE, write=True)
        for roots in (["/"], [str(tmp_path)], [str(tmp_path / "data")], ["/proc"]):
            response = await c.client.put(
                "/api/settings/files", json={"write_roots": roots}, headers=h
            )
            assert response.status == 400, roots
        assert c.config_file.read_text() == "channels: [web]\n"


async def test_files_are_for_administrators_only(tmp_path) -> None:
    async with Console(tmp_path) as c:
        response = await c.client.put(
            "/api/settings/files",
            json={"read_roots": [str(c.vault)]},
            headers=c.headers(BOB, write=True),
        )
        assert response.status == 403
