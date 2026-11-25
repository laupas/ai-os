import io
import tarfile
from datetime import UTC, datetime

import pytest

from aios.audit.audit_trail import AuditTrail
from aios.backup.backup_archive import BackupArchive
from aios.backup.backup_cipher import BackupCipher
from aios.backup.backup_contents import BackupContents
from aios.backup.backup_extractor import BackupExtractor
from aios.backup.backup_header import BackupHeader
from aios.backup.backup_maker import BackupMaker
from aios.backup.backup_unreadable import BackupUnreadable
from aios.backup.pending_restore import PendingRestore
from aios.backup.restore_audit import RestoreAudit
from aios.backup.restore_on_start import RestoreOnStart
from aios.storage.in_memory_append_log import InMemoryAppendLog
from aios.variables.secret_box import SecretBox
from tests.fakes.fake_clock import FakeClock

KEY = "a test key, long enough for one"


def _write(root, files):  # type: ignore[no-untyped-def]
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


def _read(root):  # type: ignore[no-untyped-def]
    return {
        str(p.relative_to(root)): p.read_text()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not str(p.relative_to(root)).startswith((".restore", ".before-restore-"))
    }


async def _staged(tmp_path, box: SecretBox):  # type: ignore[no-untyped-def]
    """A backup of yesterday's data dir, uploaded and checked into today's."""
    then = tmp_path / "then"
    _write(
        then, {"users/alice.json": "Alice then", "config/aios.yaml": "then", "memories/m.json": "m"}
    )
    cipher = BackupCipher(box)
    _, blob = await BackupMaker(BackupArchive(then), cipher, FakeClock()).make()
    data = tmp_path / "data"
    _write(
        data,
        {
            "users/alice.json": "Alice now",
            "users/bob.json": "Bob, added since",
            "config/aios.yaml": "now",
            "logs/aios.log": "today's log",
            "secrets.key": "an older key",
            "claude/projects/p/t.jsonl": "a transcript",
            "claude/.claude.json": "now",
        },
    )
    extractor = BackupExtractor()
    files, size, folders = extractor.check(cipher.open(blob), data)
    header = BackupCipher.header(blob)
    pending = PendingRestore(data)
    pending.stage(
        blob,
        BackupContents(
            created_at=header.created_at,
            aios_version=header.aios_version,
            key_fingerprint=header.key_fingerprint,
            files=files,
            size=size,
            folders=folders,
        ),
    )
    return data, pending, RestoreOnStart(data, pending, cipher, extractor, FakeClock())


async def test_nothing_happens_until_an_administrator_confirms(tmp_path) -> None:
    data, pending, restore = await _staged(tmp_path, SecretBox(KEY))
    before = _read(data)
    restore.run()
    assert _read(data) == before and pending.pending() is not None


async def test_a_confirmed_restore_replaces_the_data_and_keeps_the_old_beside_it(tmp_path) -> None:
    data, pending, restore = await _staged(tmp_path, SecretBox(KEY))
    pending.confirm()
    restore.run()

    assert _read(data) == {
        "claude/projects/p/t.jsonl": "a transcript",  # not in a backup: left where it is
        "config/aios.yaml": "then",
        "logs/aios.log": "today's log",
        "memories/m.json": "m",
        "secrets.key": "an older key",
        "users/alice.json": "Alice then",
    }
    record = pending.last()
    assert record is not None and record.backup.files == 3 and pending.pending() is None
    aside = data / record.kept_in
    assert record.kept_in.startswith(".before-restore-")
    assert (aside / "users" / "bob.json").read_text() == "Bob, added since"
    assert (aside / "claude" / ".claude.json").read_text() == "now"
    assert not (aside / "logs").exists()

    log = InMemoryAppendLog()
    await RestoreAudit(pending, AuditTrail(log, FakeClock())).run()
    await RestoreAudit(pending, AuditTrail(log, FakeClock())).run()  # once only
    entries = await log.read_all("audit")
    assert [e["item"] for e in entries] == ["restore"] and record.kept_in in entries[0]["detail"]


async def test_a_backup_under_a_previous_key_restores_too(tmp_path) -> None:
    old = SecretBox.new_key()
    data, pending, _ = await _staged(tmp_path, SecretBox(old))
    pending.confirm()
    cipher = BackupCipher(SecretBox(SecretBox.new_key(), [old]))
    RestoreOnStart(data, pending, cipher, BackupExtractor(), FakeClock()).run()
    assert (data / "users" / "alice.json").read_text() == "Alice then"


async def test_without_its_key_nothing_changes_and_the_reason_is_kept(tmp_path) -> None:
    data, pending, _ = await _staged(tmp_path, SecretBox(KEY))
    pending.confirm()
    before = _read(data)
    other = BackupCipher(SecretBox("another key, long enough as well"))
    RestoreOnStart(data, pending, other, BackupExtractor(), FakeClock()).run()
    assert _read(data) == before
    assert not pending.confirmed() and "AIOS_SECRETS_KEY_PREVIOUS" in (pending.failure() or "")


async def test_a_failed_unpack_puts_the_data_back(tmp_path, monkeypatch) -> None:
    data, pending, restore = await _staged(tmp_path, SecretBox(KEY))
    pending.confirm()
    before = _read(data)

    def broken(self, archive, data_dir):  # type: ignore[no-untyped-def]
        (data_dir / "users").mkdir(exist_ok=True)
        (data_dir / "users" / "half.json").write_text("half")
        raise OSError("disk full")

    monkeypatch.setattr(BackupExtractor, "extract", broken)
    restore.run()
    assert _read(data) == before
    assert not list(data.glob(".before-restore-*"))
    assert "disk full" in (pending.failure() or "")


def _archive(*members: tuple[tarfile.TarInfo, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for info, payload in members:
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _file(name: str) -> tuple[tarfile.TarInfo, bytes]:
    return tarfile.TarInfo(name), b"x"


@pytest.mark.parametrize(
    "bad",
    [
        _file("data/../outside.txt"),
        _file("/etc/passwd"),
        _file("elsewhere/users/a.json"),
        _file("data/web-sessions/a.json"),
        _file("data/.restore/confirmed"),
    ],
)
def test_a_crafted_archive_is_refused_before_anything_is_written(tmp_path, bad) -> None:
    archive = _archive(_file("data/users/alice.json"), bad)
    with pytest.raises(BackupUnreadable):
        BackupExtractor().check(archive, tmp_path)
    with pytest.raises(BackupUnreadable):
        BackupExtractor().extract(archive, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_link_out_of_the_data_dir_is_refused(tmp_path) -> None:
    link = tarfile.TarInfo("data/config/escape")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"
    with pytest.raises(BackupUnreadable):
        BackupExtractor().check(_archive(_file("data/users/a.json"), (link, b"")), tmp_path)


def test_an_archive_of_something_else_is_refused(tmp_path) -> None:
    with pytest.raises(BackupUnreadable):
        BackupExtractor().check(_archive(_file("data/photos/a.jpg")), tmp_path)
    with pytest.raises(BackupUnreadable):
        BackupExtractor().check(b"not gzip at all", tmp_path)


def test_the_header_is_kept_readable() -> None:
    header = BackupHeader(
        created_at=datetime(2026, 11, 25, tzinfo=UTC),
        aios_version="2.0.0",
        key_fingerprint="a3f9 1c07",
        left_out=[],
    )
    blob = BackupCipher(SecretBox(KEY)).seal(header, b"archive")
    assert BackupCipher.header(blob) == header
