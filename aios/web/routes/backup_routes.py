from pathlib import Path

from aiohttp import web

from aios.backup.backup_cipher import BackupCipher
from aios.backup.backup_contents import BackupContents
from aios.backup.backup_extractor import BackupExtractor
from aios.backup.backup_maker import BackupMaker
from aios.backup.backup_unreadable import BackupUnreadable
from aios.backup.pending_restore import PendingRestore
from aios.entities.users.permission import Permission
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

MAX_BACKUP_BYTES = 1024**3


class BackupRoutes(WebRoutes):
    """Settings → Backup, for administrators. A download of the data dir as one
    encrypted file; and restoring one: uploaded and checked (`PendingRestore`),
    confirmed, then applied at the next start (`RestoreOnStart`). A backup holds
    everyone's conversations and memories, so every step is a POST or DELETE (the
    CSRF header) and recorded in the audit trail (`AuditMiddleware`)."""

    def __init__(
        self,
        maker: BackupMaker,
        cipher: BackupCipher,
        extractor: BackupExtractor,
        pending: PendingRestore,
        data_dir: Path,
        max_bytes: int = MAX_BACKUP_BYTES,
    ) -> None:
        self._maker = maker
        self._cipher = cipher
        self._extractor = extractor
        self._pending = pending
        self._data_dir = Path(data_dir)
        self._max_bytes = max_bytes

    def register(self, app: web.Application) -> None:
        app.router.add_post("/api/backup", self._download)
        app.router.add_get("/api/backup/restore", self._restore_status)
        app.router.add_post("/api/backup/restore", self._upload)
        app.router.add_post("/api/backup/restore/confirm", self._confirm)
        app.router.add_delete("/api/backup/restore", self._discard)

    async def _download(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        name, blob = await self._maker.make()
        return web.Response(
            body=blob,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{name}"',
                "Cache-Control": "no-store",
            },
        )

    async def _restore_status(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        pending = self._pending.pending()
        last = self._pending.last()
        return web.json_response(
            {
                "pending": pending.model_dump(mode="json") if pending else None,
                "confirmed": self._pending.confirmed(),
                "failure": self._pending.failure(),
                "last": last.model_dump(mode="json", exclude={"recorded"}) if last else None,
            }
        )

    async def _upload(self, request: web.Request) -> web.Response:
        """Checks the backup completely (key, archive, every entry) and keeps it until
        it is confirmed; nothing in the data dir changes yet."""
        WebAuth.caller(request, Permission.ADMINISTER)
        blob = await self._body(request)
        try:
            header = BackupCipher.header(blob)
            archive = self._cipher.open(blob)
            files, size, folders = self._extractor.check(archive, self._data_dir)
        except BackupUnreadable as exc:
            raise web.HTTPBadRequest(text=f"this backup cannot be restored: {exc}") from exc
        contents = BackupContents(
            created_at=header.created_at,
            aios_version=header.aios_version,
            key_fingerprint=header.key_fingerprint,
            files=files,
            size=size,
            folders=folders,
        )
        self._pending.stage(blob, contents)
        return web.json_response(contents.model_dump(mode="json"))

    async def _confirm(self, request: web.Request) -> web.Response:
        """Applied at the next start; the console restarts ai-os right after."""
        WebAuth.caller(request, Permission.ADMINISTER)
        try:
            self._pending.confirm()
        except FileNotFoundError as exc:
            raise web.HTTPNotFound(text=str(exc)) from exc
        return web.json_response({"ok": True})

    async def _discard(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        self._pending.discard()
        return web.json_response({"ok": True})

    async def _body(self, request: web.Request) -> bytes:
        """The body, read past the server-wide limit up to this route's own."""
        body = bytearray()
        async for chunk in request.content.iter_chunked(256 * 1024):
            body += chunk
            if len(body) > self._max_bytes:
                raise web.HTTPRequestEntityTooLarge(max_size=self._max_bytes, actual_size=len(body))
        return bytes(body)
