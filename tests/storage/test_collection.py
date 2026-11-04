from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.json_file_document_store import JsonFileDocumentStore


async def test_index_survives_a_restart(tmp_path) -> None:
    definition = CollectionDefinition(name="users", entity=User)
    first = Collection(definition, JsonFileDocumentStore(tmp_path))
    await first.load()
    await first.put(User(id="u1", name="Alice", aliases=["P"]))

    second = Collection(definition, JsonFileDocumentStore(tmp_path))
    await second.load()
    found = second.find(lambda u: u.matches_name("p"))
    assert found is not None and found.id == "u1"


async def test_delete_removes_from_index(tmp_path) -> None:
    users = Collection(
        CollectionDefinition(name="users", entity=User), JsonFileDocumentStore(tmp_path)
    )
    await users.put(User(id="u1", name="Alice"))
    await users.delete("u1")
    assert users.get("u1") is None and users.is_empty()
