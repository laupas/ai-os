from pathlib import Path
from typing import Any

from pydantic import BaseModel

from aios.connectors.code_connectors import CODE_KEY
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.store.store_kind import StoreKind
from aios.store.store_meta import StoreMeta
from aios.store.store_ref import StoreRef


class StoreItem(BaseModel):
    """One agent, skill, connector or trigger a source offers: its document as the
    configuration repository holds it, and its `store:` block."""

    source: str
    kind: StoreKind
    id: str
    document: dict[str, Any]
    meta: StoreMeta = StoreMeta()
    code_folder: Path | None = None
    """A code connector's folder in the source, copied into `code/` on install."""

    @property
    def ref(self) -> StoreRef:
        return StoreRef(kind=self.kind, id=self.id)

    @property
    def title(self) -> str:
        return self.meta.title or str(self.document.get("name") or self.id)

    @property
    def description(self) -> str:
        return str(self.document.get("description") or "")

    @property
    def code_name(self) -> str | None:
        config = self.document.get("config") if self.kind is StoreKind.CONNECTOR else None
        return str(config[CODE_KEY]) if isinstance(config, dict) and CODE_KEY in config else None

    def requires(self) -> list[StoreRef]:
        """What it needs besides itself: what its `store:` block names, an agent's
        connectors and skills, a trigger's agent. In that order, without repeats."""
        refs = [StoreRef.parse(r) for r in self.meta.requires]
        if self.kind is StoreKind.AGENT:
            refs += [
                StoreRef(kind=StoreKind.CONNECTOR, id=c)
                for c in self.document.get("connectors") or {}
                if c != ConnectorCatalog.BUILTIN
            ]
            skills = self.document.get("skills") or []
            refs += [StoreRef(kind=StoreKind.SKILL, id=s) for s in skills]
        if self.kind is StoreKind.TRIGGER and self.document.get("agent"):
            refs.append(StoreRef(kind=StoreKind.AGENT, id=str(self.document["agent"])))
        return list(dict.fromkeys(r for r in refs if r != self.ref))
