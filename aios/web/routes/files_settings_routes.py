import os
from pathlib import Path
from typing import Any

import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.approvals.file_root_guard import FileRootGuard
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.entities.users.permission import Permission
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.files_request import FilesRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

MOUNTINFO = Path("/proc/self/mountinfo")
# Files Docker mounts into every container; never a folder anyone means.
DOCKER_FILES = {"/etc/hosts", "/etc/hostname", "/etc/resolv.conf"}


class FilesSettingsRoutes(WebRoutes):
    """The folders agents' file tools may read and write (`files` in aios.yaml).
    Administrators only.

    A folder `FileRootGuard` refuses (`/`, the data dir, ai-os's code, /proc, …)
    is refused here too, with the reason; `FileAccessRule` would leave it out
    anyway. Each folder is shown with whether it exists where ai-os runs, and the
    folders mounted into the container are offered, since in Docker nothing else
    is there to give. Applies after a restart.
    """

    def __init__(
        self, config: AiosYamlFile, guard: FileRootGuard, mountinfo: Path = MOUNTINFO
    ) -> None:
        self._config = config
        self._guard = guard
        self._mountinfo = Path(mountinfo)
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings/files", self._read)
        app.router.add_post("/api/settings/files/check", self._check)
        app.router.add_put("/api/settings/files", self._save)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        files = self._current()
        roots = files.get("read_roots", []) + files.get("write_roots", [])
        return web.json_response(
            {
                "read_roots": files.get("read_roots", []),
                "write_roots": files.get("write_roots", []),
                "paths": {r: self._status(r) for r in roots},
                "mounts": self._mounts(),
                "protected": self._guard.protected,
            }
        )

    async def _check(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, FilesRequest)
        roots = body.read_roots + body.write_roots
        return web.json_response({"paths": {r: self._status(r) for r in roots}})

    async def _save(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, FilesRequest)
        read = self._tidy(body.read_roots)
        write = self._tidy(body.write_roots)
        problems = [p for r in read + write if (p := self._guard.problem(r))]
        if problems:
            raise web.HTTPBadRequest(text="; ".join(problems))
        section: dict[str, Any] = {}
        if read:
            section["read_roots"] = read
        if write:
            section["write_roots"] = write
        text = self._editor.replace_section(self._config.read(), "files", section or None)
        try:
            AppConfig.model_validate(yaml.safe_load(text) or {})
        except (yaml.YAMLError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        await self._config.write(text, "aios.yaml: files")
        return web.json_response({"ok": True})

    def _status(self, root: str) -> dict[str, Any]:
        problem = self._guard.problem(root)
        real = os.path.realpath(root) if os.path.isabs(root) else None
        return {
            "problem": problem,
            "exists": bool(real and os.path.isdir(real)),
            "real": real if real and real != root.rstrip(os.sep) else None,
        }

    def _mounts(self) -> list[str]:
        """Folders mounted into this container that may be given: what Docker
        offers to share, without the system's own."""
        try:
            lines = self._mountinfo.read_text("utf-8").splitlines()
        except OSError:
            return []
        points = {line.split()[4] for line in lines if len(line.split()) > 4}
        return sorted(
            p
            for p in points
            if p not in DOCKER_FILES and os.path.isdir(p) and self._guard.problem(p) is None
        )

    @staticmethod
    def _tidy(roots: list[str]) -> list[str]:
        seen: list[str] = []
        for root in roots:
            root = root.strip().rstrip("/") or root.strip()
            if root and root not in seen:
                seen.append(root)
        return seen

    def _current(self) -> dict[str, list[str]]:
        try:
            loaded = yaml.safe_load(self._config.read()) or {}
        except yaml.YAMLError:
            return {}
        files = loaded.get("files") if isinstance(loaded, dict) else None
        return files if isinstance(files, dict) else {}
