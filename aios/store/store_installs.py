import yaml
from pydantic import ValidationError

from aios.common.clock import Clock
from aios.config_repo.git_document_store import GitDocumentStore
from aios.entities.store.store_install_record import StoreInstallRecord
from aios.entities.users.user import User
from aios.store.store_item import StoreItem
from aios.store.store_ref import StoreRef

RECORDS = ".aios-store.yaml"


class StoreInstalls:
    """Where each item installed from the Store came from, and its version, in one
    file of the configuration repository, so a branch or a clone knows it too. An
    item made by hand, or installed before versions were kept, has no record."""

    def __init__(self, config_store: GitDocumentStore, clock: Clock) -> None:
        self._store = config_store
        self._clock = clock

    def get(self, ref: StoreRef) -> StoreInstallRecord | None:
        return self._all().get(str(ref))

    async def record(self, items: list[StoreItem], user: User) -> None:
        """Written with the install, inside its commit."""
        records = self._all()
        for item in items:
            records[str(item.ref)] = StoreInstallRecord(
                source=item.source,
                version=item.meta.version,
                installed_at=self._clock.now(),
                installed_by=user.name,
            )
        await self._write(records)

    async def _write(self, records: dict[str, StoreInstallRecord]) -> None:
        data = {k: v.model_dump(mode="json") for k, v in sorted(records.items())}
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False) if data else ""
        await self._store.write_file(RECORDS, text, "")

    async def forget(self, refs: list[StoreRef]) -> None:
        """Written with the uninstall, inside its commit."""
        records = self._all()
        if not any(str(r) in records for r in refs):
            return
        for ref in refs:
            records.pop(str(ref), None)
        await self._write(records)

    def _all(self) -> dict[str, StoreInstallRecord]:
        try:
            data = yaml.safe_load(self._store.read_file(RECORDS) or "") or {}
            return {k: StoreInstallRecord.model_validate(v) for k, v in data.items()}
        except (yaml.YAMLError, ValidationError, AttributeError):
            return {}
