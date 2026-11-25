import io
import os
import tarfile

import pytest

from aios.backup.backup_archive import LEFT_OUT, BackupArchive
from aios.backup.backup_cipher import BackupCipher
from aios.backup.backup_maker import BackupMaker
from aios.backup.backup_unreadable import BackupUnreadable
from aios.variables.secret_box import SecretBox
from tests.fakes.fake_clock import FakeClock


def _data_dir(tmp_path):  # type: ignore[no-untyped-def]
    data = tmp_path / "data"
    files = {
        "users/alice.json": '{"name": "Alice Example"}',
        "config/aios.yaml": "channels: [web]\n",
        "config/.git/HEAD": "ref: refs/heads/dev\n",
        "claude/.claude.json": "{}",
        "logs/aios.log": "a line",
        "web-sessions/abc.json": "{}",
        "variable-files/GMAIL_KEYS": "decrypted",
        "secrets.key": "an older key",
        "claude/projects/p/turn.jsonl": "a transcript",
        "claude/sessions/s.json": "{}",
        "claude/backups/c.json": "{}",
        "users/.tmp-123.json": "half",
        ".DS_Store": "litter",
    }
    for name, text in files.items():
        (data / name).parent.mkdir(parents=True, exist_ok=True)
        (data / name).write_text(text)
    os.symlink(tmp_path / "outside.txt", data / "config" / "skills-link")
    (tmp_path / "outside.txt").write_text("not ours")
    return data


def _names(archive: bytes) -> dict[str, tarfile.TarInfo]:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        return {m.name: m for m in tar.getmembers()}


async def test_a_backup_holds_the_data_dir_without_what_must_not_travel(tmp_path) -> None:
    box = SecretBox("a test key, long enough for one")
    cipher = BackupCipher(box)
    name, blob = await BackupMaker(BackupArchive(_data_dir(tmp_path)), cipher, FakeClock()).make()

    assert name.startswith("aios-backup-") and name.endswith(".aiosbackup")
    assert box.fingerprint().replace(" ", "") in name
    header = BackupCipher.header(blob)
    assert header.key_fingerprint == box.fingerprint() and header.left_out == list(LEFT_OUT)
    assert b"Alice Example" not in blob  # sealed

    members = _names(cipher.open(blob))
    assert {"data/users/alice.json", "data/config/aios.yaml", "data/config/.git/HEAD"} <= set(
        members
    )
    assert "data/claude/.claude.json" in members  # the CLI's sign-ins come along
    for gone in (
        "logs",
        "web-sessions",
        "variable-files",
        "secrets.key",
        "claude/projects",
        "claude/sessions",
        "claude/backups",
        "users/.tmp-123.json",
        ".DS_Store",
    ):
        assert not any(m == f"data/{gone}" or m.startswith(f"data/{gone}/") for m in members)
    link = members["data/config/skills-link"]
    assert link.issym() and link.uid == 0 and link.uname == ""  # a link, never what it points at


async def test_only_the_same_key_opens_a_backup_and_nothing_can_be_altered(tmp_path) -> None:
    data = _data_dir(tmp_path)
    sealed = BackupCipher(SecretBox("a test key, long enough for one"))
    _, blob = await BackupMaker(BackupArchive(data), sealed, FakeClock()).make()

    other = BackupCipher(SecretBox("another key, long enough as well"))
    with pytest.raises(BackupUnreadable) as caught:
        other.open(blob)
    assert sealed.fingerprint() in str(caught.value) and other.fingerprint() in str(caught.value)

    forged = blob.replace(b'"format":1', b'"format":2', 1)
    assert forged != blob
    with pytest.raises(BackupUnreadable):
        sealed.open(forged)  # the header is bound to the contents
    with pytest.raises(BackupUnreadable):
        sealed.open(b"PK\x03\x04 a zip file")
    with pytest.raises(BackupUnreadable):
        sealed.open(blob[:60])
