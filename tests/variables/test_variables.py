import json

import pytest
from cryptography.fernet import Fernet

from aios.agents.catalog_error import CatalogError
from aios.entities.variables.variable import Variable
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.json_file_document_store import JsonFileDocumentStore
from aios.variables.secret_box import SecretBox
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from tests.fakes.fake_clock import FakeClock


def _world(tmp_path, key: str | None = None):  # type: ignore[no-untyped-def]
    store = JsonFileDocumentStore(tmp_path / "data")
    variables: Collection[Variable] = Collection(
        CollectionDefinition(name="variables", entity=Variable), store
    )
    box = SecretBox(key, tmp_path / "data" / "secrets.key")
    catalog = VariableCatalog(variables, box, FakeClock())
    resolver = VariableResolver(variables, box, tmp_path / "files")
    return catalog, resolver


async def test_a_secret_is_encrypted_at_rest_and_filled_into_a_config(tmp_path) -> None:
    catalog, resolver = _world(tmp_path, Fernet.generate_key().decode())
    await catalog.save("API_TOKEN", "s3cret", True, False, "", "Alice")
    stored = (tmp_path / "data" / "variables" / "API_TOKEN.json").read_text()
    assert "s3cret" not in stored
    config = {"headers": {"Authorization": "Bearer ${API_TOKEN}"}, "args": ["${MISSING}"]}
    assert resolver.expand(config) == {
        "headers": {"Authorization": "Bearer s3cret"},
        "args": ["${MISSING}"],  # left visible, so the failure names it
    }
    assert resolver.missing(config) == ["MISSING"]


async def test_a_file_variable_is_written_once_per_value(tmp_path) -> None:
    catalog, resolver = _world(tmp_path)
    keys = json.dumps({"installed": {"client_id": "x"}})
    await catalog.save("GMAIL_KEYS", keys, True, True, "", "Alice")
    path = resolver.expand("${file:GMAIL_KEYS}")
    assert (
        open(path).read() == keys
        and oct((tmp_path / "files" / "GMAIL_KEYS").stat().st_mode)[-3:] == "600"
    )
    open(path, "w").write("refreshed by the server")
    resolver.expand("${file:GMAIL_KEYS}")
    assert open(path).read() == "refreshed by the server"  # kept: the value did not change
    await catalog.save("GMAIL_KEYS", "{}", True, True, "", "Alice")
    resolver.expand("${file:GMAIL_KEYS}")
    assert open(path).read() == "{}"  # a new value replaces it


async def test_a_secret_is_edited_without_its_value_and_the_environment_is_the_fallback(
    tmp_path, monkeypatch
) -> None:
    catalog, resolver = _world(tmp_path)
    await catalog.save("TOKEN", "one", True, False, "first", "Alice")
    await catalog.save("TOKEN", None, True, False, "second", "Alice")
    assert resolver.value_of("TOKEN") == "one" and catalog.get("TOKEN").description == "second"  # type: ignore[union-attr]
    with pytest.raises(CatalogError):
        await catalog.save("TOKEN", None, False, False, "", "Alice")  # unsecret needs the value
    with pytest.raises(CatalogError):
        await catalog.save("lower", "x", False, False, "", "Alice")
    monkeypatch.setenv("FROM_ENV", "env-value")
    assert resolver.expand("${FROM_ENV}") == "env-value"


def test_a_generated_password_works_as_the_key_and_stays_the_same_key(tmp_path) -> None:
    password = "x" * 100
    box = SecretBox(password, tmp_path / "unused.key")
    token = box.encrypt("s3cret")
    assert SecretBox(password, tmp_path / "unused.key").decrypt(token) == "s3cret"
    assert SecretBox("y" * 100, tmp_path / "unused.key").decrypt(token) is None
    assert not (tmp_path / "unused.key").exists()
    fernet_key = Fernet.generate_key().decode()
    assert SecretBox.key_from(fernet_key) == fernet_key.encode()
