import pytest

from aios.storage.document_store import DocumentStore
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.storage.json_file_document_store import JsonFileDocumentStore


@pytest.fixture(params=["json_file", "in_memory"])
def store(request: pytest.FixtureRequest, tmp_path) -> DocumentStore:
    if request.param == "json_file":
        return JsonFileDocumentStore(tmp_path)
    return InMemoryDocumentStore()


async def test_put_then_get(store: DocumentStore) -> None:
    await store.put("users", "u1", {"id": "u1", "name": "Alice"})
    assert await store.get("users", "u1") == {"id": "u1", "name": "Alice"}


async def test_get_missing_is_none(store: DocumentStore) -> None:
    assert await store.get("users", "nobody") is None


async def test_put_replaces(store: DocumentStore) -> None:
    await store.put("users", "u1", {"id": "u1", "name": "A"})
    await store.put("users", "u1", {"id": "u1", "name": "B"})
    assert await store.list("users") == [{"id": "u1", "name": "B"}]


async def test_list_is_per_collection(store: DocumentStore) -> None:
    await store.put("users", "u1", {"id": "u1"})
    await store.put("roles", "r1", {"id": "r1"})
    assert await store.list("users") == [{"id": "u1"}]
    assert await store.list("empty") == []


async def test_delete(store: DocumentStore) -> None:
    await store.put("users", "u1", {"id": "u1"})
    await store.delete("users", "u1")
    await store.delete("users", "u1")  # deleting twice is fine
    assert await store.get("users", "u1") is None


@pytest.mark.parametrize("bad", ["../etc", "a/b", "", ".hidden"])
async def test_rejects_ids_that_escape_the_data_dir(store: DocumentStore, bad: str) -> None:
    with pytest.raises(ValueError):
        await store.put("users", bad, {})


async def test_json_file_store_leaves_no_temp_files(tmp_path) -> None:
    store = JsonFileDocumentStore(tmp_path)
    await store.put("users", "u1", {"id": "u1"})
    assert sorted(p.name for p in (tmp_path / "users").iterdir()) == ["u1.json"]
