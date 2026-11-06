from __future__ import annotations

import json
from typing import Any

from aios.audit.audit_policy import AuditPolicy
from aios.audit.audit_trail import AuditTrail
from aios.entities.audit.audit_action import AuditAction
from aios.storage.document_store import DocumentStore

MAX_VALUE_CHARS = 80


class AuditedDocumentStore(DocumentStore):
    """Records every real change to the collections in `policies` in the audit
    trail, then passes it on. Other collections pass through untouched.

    Wraps the store rather than each caller, so a change is recorded however it
    was made: the console, an agent's `data_put`, a history restore.
    """

    def __init__(
        self, inner: DocumentStore, trail: AuditTrail, policies: dict[str, AuditPolicy]
    ) -> None:
        self._inner = inner
        self._trail = trail
        self._policies = policies

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        return await self._inner.get(collection, doc_id)

    async def list(self, collection: str) -> list[dict[str, Any]]:
        return await self._inner.list(collection)

    async def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        policy = self._policies.get(collection)
        if policy is None:
            await self._inner.put(collection, doc_id, data)
            return
        before = await self._inner.get(collection, doc_id)
        await self._inner.put(collection, doc_id, data)
        if before is None:
            await self._trail.record(collection, doc_id, AuditAction.CREATED)
            return
        changed = [
            k
            for k in sorted(before.keys() | data.keys())
            if k not in policy.ignored_fields and before.get(k) != data.get(k)
        ]
        if not changed:
            return
        detail = self._detail(changed, before, data) if policy.show_values else None
        await self._trail.record(collection, doc_id, AuditAction.CHANGED, changed, detail)

    async def delete(self, collection: str, doc_id: str) -> None:
        if collection not in self._policies:
            await self._inner.delete(collection, doc_id)
            return
        before = await self._inner.get(collection, doc_id)
        await self._inner.delete(collection, doc_id)
        if before is not None:
            await self._trail.record(collection, doc_id, AuditAction.DELETED)

    @classmethod
    def _detail(cls, fields: list[str], before: dict[str, Any], after: dict[str, Any]) -> str:
        return "; ".join(
            f"{f}: {cls._show(before.get(f))} → {cls._show(after.get(f))}" for f in fields
        )

    @staticmethod
    def _show(value: Any) -> str:
        text = json.dumps(value, ensure_ascii=False, default=str)
        return text if len(text) <= MAX_VALUE_CHARS else text[: MAX_VALUE_CHARS - 1] + "…"
