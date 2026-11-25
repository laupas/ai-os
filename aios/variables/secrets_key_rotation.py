import logging

from aios.audit.audit_trail import AuditTrail
from aios.bootstrap.startup_step import StartupStep
from aios.entities.audit.audit_action import AuditAction
from aios.variables.encrypted_fields import EncryptedFields
from aios.variables.secret_box import SecretBox
from aios.variables.secrets_key_origin import SecretsKeyOrigin
from aios.variables.secrets_key_source import SecretsKeySource
from aios.variables.secrets_status import SecretsStatus

log = logging.getLogger(__name__)


class SecretsKeyRotation(StartupStep):
    """At every start, moves each stored secret that a previous key opens onto the key
    in use, so a key is replaced by setting the new one and restarting. Safe to
    interrupt: what has moved stays moved, the rest moves at the next start. A secret
    no key opens is left as it is and listed (`status`), never deleted.

    Once the key comes from the setting and nothing needs it, the key file of an older
    ai-os is removed from the data dir.
    """

    def __init__(
        self,
        box: SecretBox,
        source: SecretsKeySource,
        holders: list[EncryptedFields],
        trail: AuditTrail,
    ) -> None:
        self._box = box
        self._source = source
        self._holders = holders
        self._trail = trail

    async def run(self) -> None:
        moved = 0
        for holder in self._holders:
            for document in holder.collection.all():
                if not holder.applies(document):
                    continue
                update = {}
                for field in holder.fields:
                    token = getattr(document, field)
                    if not token:
                        continue
                    renewed = self._box.rekey(token)
                    if renewed is not None and renewed != token:
                        update[field] = renewed
                if update:
                    await holder.collection.put(document.model_copy(update=update))
                    moved += 1
        if moved:
            log.info("moved %d secrets onto the key %s", moved, self._box.fingerprint())
            await self._trail.record(
                "security",
                "secrets key",
                AuditAction.PERFORMED,
                detail=f"{moved} moved onto key {self._box.fingerprint()}",
            )
        if self._source.origin() is SecretsKeyOrigin.SETTING and self._source.legacy_file():
            self._source.remove_legacy_file()
            log.info("removed the key file of an older ai-os from the data dir")
            await self._trail.record(
                "security", "secrets key file", AuditAction.DELETED, detail="secrets.key"
            )
        if self._source.origin() is SecretsKeyOrigin.DATA_DIR:
            log.warning(
                "the secrets key comes from the data dir: set it as AIOS_SECRETS_KEY "
                "(Settings → Security shows it) and restart"
            )
        unreadable = self.status().unreadable
        if unreadable:
            log.error("no key opens %s", ", ".join(unreadable))

    def status(self) -> SecretsStatus:
        total = on_previous = 0
        unreadable: list[str] = []
        for holder in self._holders:
            for document in holder.collection.all():
                if not holder.applies(document):
                    continue
                tokens = [t for f in holder.fields if (t := getattr(document, f))]
                if not tokens:
                    continue
                total += 1
                if all(self._box.is_current(t) for t in tokens):
                    continue
                if all(self._box.rekey(t) is not None for t in tokens):
                    on_previous += 1
                else:
                    unreadable.append(f"{holder.label} {document.id}")
        return SecretsStatus(
            origin=self._source.origin(),
            fingerprint=self._box.fingerprint(),
            previous_fingerprints=self._box.previous_fingerprints(),
            legacy_file=self._source.legacy_file() is not None,
            total=total,
            on_previous=on_previous,
            unreadable=unreadable,
        )
