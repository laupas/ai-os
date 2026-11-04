import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from aios.storage.append_log import AppendLog
from aios.storage.storage_name import StorageName

log = logging.getLogger(__name__)


class JsonlAppendLog(AppendLog):
    """One JSON object per line in `<root>/<log>.jsonl`.

    A crash can leave a torn last line; it is skipped when reading, so everything
    before it stays readable.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    async def append(self, log_name: str, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        await asyncio.to_thread(self._append, self._file(log_name), line)

    async def read_all(self, log_name: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._read, self._file(log_name))

    async def delete(self, log_name: str) -> None:
        await asyncio.to_thread(self._delete, self._file(log_name))

    def _delete(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        # A conversation's log is alone in its folder; drop the folder when empty.
        if path.parent != self._root and path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()

    def _file(self, log_name: str) -> Path:
        return self._root / f"{StorageName.check_path(log_name)}.jsonl"

    @staticmethod
    def _append(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("skipping unreadable line %d in %s", number, path)
        return records
