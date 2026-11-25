import pytest

from aios.audit.audit_trail import AuditTrail
from aios.config.settings import Settings
from aios.connectors.connector_tokens import SECRET_FIELDS, ConnectorTokens
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.git.git_remote import GitRemote
from aios.entities.variables.variable import Variable
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_append_log import InMemoryAppendLog
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.variables.encrypted_fields import EncryptedFields
from aios.variables.legacy_variable_files_removal import LegacyVariableFilesRemoval
from aios.variables.secret_box import SecretBox
from aios.variables.secrets_key_missing import SecretsKeyMissing
from aios.variables.secrets_key_origin import SecretsKeyOrigin
from aios.variables.secrets_key_rotation import SecretsKeyRotation
from aios.variables.secrets_key_source import SecretsKeySource
from tests.fakes.fake_clock import FakeClock

OLD = SecretBox.new_key()
NEW = SecretBox.new_key()


def test_the_key_comes_from_the_setting_and_nowhere_else(tmp_path) -> None:
    source = SecretsKeySource(NEW, None, tmp_path / "secrets.key")
    assert source.current() == NEW and source.previous() == []
    assert source.origin() is SecretsKeyOrigin.SETTING
    with pytest.raises(SecretsKeyMissing):
        SecretsKeySource(None, None, tmp_path / "secrets.key").current()
    with pytest.raises(SecretsKeyMissing):
        SecretsKeySource("", OLD, tmp_path / "secrets.key").current()  # empty counts as unset
    assert not (tmp_path / "secrets.key").exists()  # nothing generated


def test_an_older_key_file_is_used_until_the_setting_takes_over(tmp_path) -> None:
    (tmp_path / "secrets.key").write_text(OLD + "\n")
    alone = SecretsKeySource(None, None, tmp_path / "secrets.key")
    assert alone.current() == OLD and alone.origin() is SecretsKeyOrigin.DATA_DIR
    # Set to another key, the file is one more previous key; set to itself, none.
    other = SecretsKeySource(NEW, "a key before", tmp_path / "secrets.key")
    assert other.current() == NEW and other.previous() == ["a key before", OLD]
    assert SecretsKeySource(OLD, None, tmp_path / "secrets.key").previous() == []


def test_a_previous_key_opens_but_never_encrypts() -> None:
    token = SecretBox(OLD).encrypt("s3cret")
    box = SecretBox(NEW, [OLD])
    assert box.decrypt(token) == "s3cret" and not box.is_current(token)
    renewed = box.rekey(token)
    assert renewed and box.is_current(renewed) and SecretBox(NEW).decrypt(renewed) == "s3cret"
    assert SecretBox(OLD).decrypt(renewed) is None
    assert box.rekey(SecretBox(SecretBox.new_key()).encrypt("x")) is None
    assert box.fingerprint() == SecretBox.fingerprint_of(NEW) != SecretBox.fingerprint_of(OLD)
    assert box.previous_fingerprints() == [SecretBox.fingerprint_of(OLD)]
    assert NEW not in box.fingerprint().replace(" ", "")


def _holders(store: InMemoryDocumentStore):  # type: ignore[no-untyped-def]
    variables: Collection[Variable] = Collection(
        CollectionDefinition(name="variables", entity=Variable), store
    )
    tokens: Collection[ConnectorToken] = Collection(
        CollectionDefinition(name="connector-tokens", entity=ConnectorToken), store
    )
    remotes: Collection[GitRemote] = Collection(
        CollectionDefinition(name="git-remotes", entity=GitRemote), store
    )
    return (
        variables,
        tokens,
        remotes,
        [
            EncryptedFields(
                collection=variables,
                fields=("value",),
                label="variable",
                applies=lambda v: v.secret,
            ),
            EncryptedFields(
                collection=tokens,
                fields=SECRET_FIELDS,
                label="connector sign-in",
                applies=lambda t: t.encrypted,
            ),
            EncryptedFields(
                collection=remotes, fields=("token", "private_key"), label="configuration remote"
            ),
        ],
    )


async def test_a_new_key_reaches_every_stored_secret_at_start(tmp_path) -> None:
    store = InMemoryDocumentStore()
    variables, tokens, remotes, holders = _holders(store)
    old = SecretBox(OLD)
    await variables.put(Variable(id="API_TOKEN", value=old.encrypt("s3cret"), secret=True))
    await variables.put(Variable(id="REGION", value="eu", secret=False))
    stray = SecretBox(SecretBox.new_key()).encrypt("lost")
    await variables.put(Variable(id="LOST", value=stray, secret=True))
    await ConnectorTokens(tokens, old).put(
        ConnectorToken(
            id="",
            connector="gmail",
            access_token="access",
            refresh_token="refresh",
            token_endpoint="https://example/token",
            client_id="cid",
        )
    )
    await remotes.put(GitRemote(url="git@example:c.git", auth="token", token=old.encrypt("ghp")))
    (tmp_path / "secrets.key").write_text(OLD)  # an older ai-os's file, now in the previous keys
    source = SecretsKeySource(NEW, None, tmp_path / "secrets.key")
    box = SecretBox(source.current(), source.previous())
    log = InMemoryAppendLog()
    rotation = SecretsKeyRotation(box, source, holders, AuditTrail(log, FakeClock()))

    before = rotation.status()
    assert (before.total, before.on_previous, before.unreadable) == (4, 3, ["variable LOST"])
    await rotation.run()

    after = rotation.status()
    assert (after.total, after.on_previous, after.unreadable) == (4, 0, ["variable LOST"])
    assert SecretBox(NEW).decrypt(variables.get("API_TOKEN").value) == "s3cret"  # type: ignore[union-attr]
    assert variables.get("REGION").value == "eu"  # type: ignore[union-attr]
    assert variables.get("LOST").value == stray  # type: ignore[union-attr]  # kept, not deleted
    assert ConnectorTokens(tokens, SecretBox(NEW)).shared("gmail").access_token == "access"  # type: ignore[union-attr]
    assert SecretBox(NEW).decrypt(remotes.get("origin").token) == "ghp"  # type: ignore[arg-type,union-attr]
    assert not (tmp_path / "secrets.key").exists() and not after.legacy_file
    entries = await log.read_all("audit")
    assert [e["item"] for e in entries] == ["secrets key", "secrets key file"]
    assert entries[0]["detail"] == f"3 moved onto key {box.fingerprint()}"
    await rotation.run()  # nothing left to move: no further entry
    assert len(await log.read_all("audit")) == 2


async def test_the_key_file_stays_while_it_is_the_key_in_use(tmp_path) -> None:
    (tmp_path / "secrets.key").write_text(OLD)
    source = SecretsKeySource(None, None, tmp_path / "secrets.key")
    _, _, _, holders = _holders(InMemoryDocumentStore())
    rotation = SecretsKeyRotation(
        SecretBox(source.current()), source, holders, AuditTrail(InMemoryAppendLog(), FakeClock())
    )
    await rotation.run()
    assert (tmp_path / "secrets.key").exists()
    assert rotation.status().origin is SecretsKeyOrigin.DATA_DIR and rotation.status().legacy_file


async def test_decrypted_files_leave_the_data_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIOS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("AIOS_VARIABLE_FILES_DIR", raising=False)
    settings = Settings()
    assert tmp_path / "data" not in settings.variable_files_dir().parents
    legacy = settings.legacy_variable_files_dir()
    legacy.mkdir(parents=True)
    (legacy / "GMAIL_KEYS").write_text("{}")
    await LegacyVariableFilesRemoval(legacy, settings.variable_files_dir()).run()
    assert not legacy.exists()
    # Unless someone points the files at that very folder.
    legacy.mkdir()
    await LegacyVariableFilesRemoval(legacy, legacy).run()
    assert legacy.exists()
