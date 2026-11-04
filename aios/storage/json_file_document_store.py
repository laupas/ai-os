from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from aios.storage.document_store import DocumentStore
from aios.storage.storage_name import StorageName

log = logging.getLogger(__name__)


class JsonFileDocumentStore(DocumentStore):
    """One JSON file per document: `<root>/<collection>/<id>.json`.

    Writes go to a temp file that is renamed into place, so a reader never sees a
    half-written document. Assumes a single writing process.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._read, self._file(collection, doc_id))

    async def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._write, self._file(collection, doc_id), data)

    async def delete(self, collection: str, doc_id: str) -> None:
        await asyncio.to_thread(self._file(collection, doc_id).unlink, True)

    async def list(self, collection: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list, self._dir(collection))

    def _dir(self, collection: str) -> Path:
        return self._root / StorageName.check(collection)

    def _file(self, collection: str, doc_id: str) -> Path:
        return self._dir(collection) / f"{StorageName.check(doc_id)}.json"

    @staticmethod
    def _read(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    @staticmethod
    def _list(directory: Path) -> list[dict[str, Any]]:
        if not directory.is_dir():
            return []
        documents = []
        for path in sorted(directory.glob("*.json")):
            if path.name.startswith("."):
                continue
            try:
                documents.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                log.error("skipping unreadable document %s", path)
        return documents
