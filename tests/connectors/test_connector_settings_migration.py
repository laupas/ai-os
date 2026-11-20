from aios.connectors.connector_settings_migration import ConnectorSettingsMigration
from aios.entities.connectors.connector import Connector
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.web.aios_yaml_file import AiosYamlFile

YAML = """\
timezone: Europe/Zurich

# Limits that must hold.
connectors:
  crypto:
    settings:
      max_chf_per_day: 300
  gone:
    settings: {x: 1}

files:
  read_roots: []
"""


async def test_fixed_settings_move_onto_the_connector_and_out_of_aios_yaml(tmp_path) -> None:
    file = tmp_path / "aios.yaml"
    file.write_text(YAML)
    store: Collection[Connector] = Collection(
        CollectionDefinition(name="connectors", entity=Connector), InMemoryDocumentStore()
    )
    await store.put(
        Connector(id="crypto", config={"code": "crypto", "settings": {"max_chf_per_day": 900}})
    )
    migration = ConnectorSettingsMigration(AiosYamlFile(file), store)
    await migration.run()
    assert store.get("crypto").config["settings"] == {"max_chf_per_day": 300}  # type: ignore[union-attr]
    assert file.read_text() == "timezone: Europe/Zurich\n\nfiles:\n  read_roots: []\n"
    await migration.run()  # nothing left to do
    assert file.read_text() == "timezone: Europe/Zurich\n\nfiles:\n  read_roots: []\n"
