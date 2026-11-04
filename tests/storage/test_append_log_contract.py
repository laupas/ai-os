import pytest

from aios.storage.append_log import AppendLog
from aios.storage.in_memory_append_log import InMemoryAppendLog
from aios.storage.jsonl_append_log import JsonlAppendLog


@pytest.fixture(params=["jsonl", "in_memory"])
def log(request: pytest.FixtureRequest, tmp_path) -> AppendLog:
    if request.param == "jsonl":
        return JsonlAppendLog(tmp_path)
    return InMemoryAppendLog()


async def test_appends_in_order(log: AppendLog) -> None:
    await log.append("conversations/c1/messages", {"n": 1})
    await log.append("conversations/c1/messages", {"n": 2})
    assert await log.read_all("conversations/c1/messages") == [{"n": 1}, {"n": 2}]


async def test_missing_log_is_empty(log: AppendLog) -> None:
    assert await log.read_all("conversations/none/messages") == []


async def test_rejects_paths_that_escape(log: AppendLog) -> None:
    with pytest.raises(ValueError):
        await log.append("conversations/../x", {})


async def test_jsonl_skips_a_torn_last_line(tmp_path) -> None:
    log = JsonlAppendLog(tmp_path)
    await log.append("c/messages", {"n": 1})
    with (tmp_path / "c" / "messages.jsonl").open("a") as handle:
        handle.write('{"n": 2, "te')  # crash mid-write
    assert await log.read_all("c/messages") == [{"n": 1}]


async def test_delete_removes_the_log(log: AppendLog) -> None:
    await log.append("conversations/c1/messages", {"n": 1})
    await log.delete("conversations/c1/messages")
    await log.delete("conversations/never/messages")  # a missing log is fine
    assert await log.read_all("conversations/c1/messages") == []


async def test_jsonl_delete_drops_the_emptied_folder(tmp_path) -> None:
    log = JsonlAppendLog(tmp_path)
    await log.append("conversations/c1/messages", {"n": 1})
    await log.delete("conversations/c1/messages")
    assert not (tmp_path / "conversations" / "c1").exists()
    assert (tmp_path / "conversations").exists()
