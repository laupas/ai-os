import re

from aiohttp import web

from aios.config_repo.repository_conflict import RepositoryConflict
from aios.config_repo.repository_files import RepositoryFiles
from aios.entities.users.permission import Permission
from aios.web.file_write_request import FileWriteRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
MAX_LIMIT = 200


class RepositoryRoutes(WebRoutes):
    """The configuration repository as files: browse any branch, read a file, its
    history and any commit's diff, and write or delete a file as a commit.
    Administrators only.

    Writing a code connector's files here runs code on this machine, which an
    administrator could already do with a command connector; agents never reach
    these routes.
    """

    def __init__(self, files: RepositoryFiles) -> None:
        self._files = files

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/repository/tree", self._tree)
        app.router.add_get("/api/repository/file", self._read)
        app.router.add_get("/api/repository/history", self._history)
        app.router.add_get("/api/repository/remote", self._remote)
        app.router.add_get("/api/repository/commits/{commit}", self._diff)
        app.router.add_put("/api/repository/file", self._write)

    async def _tree(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        current = self._files.current_branch()
        ref = request.query.get("ref") or current
        files = await self._run(self._files.tree(ref))
        return web.json_response({"ref": ref, "current": current, "files": files})

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        ref = request.query.get("ref") or self._files.current_branch()
        try:
            return web.json_response(await self._run(self._files.read(ref, request.query["path"])))
        except (KeyError, FileNotFoundError) as exc:
            raise web.HTTPNotFound(text="no such file") from exc

    async def _history(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        ref = request.query.get("ref") or self._files.current_branch()
        try:
            skip = max(0, int(request.query.get("skip", "0")))
            limit = max(1, min(int(request.query.get("limit", "50")), MAX_LIMIT))
        except ValueError as exc:
            raise web.HTTPBadRequest(text="skip and limit are numbers") from exc
        path = request.query.get("path") or None
        commits = await self._run(self._files.history(ref, path, skip, limit))
        return web.json_response({"commits": commits, "more": len(commits) == limit})

    async def _remote(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        branch = request.query.get("branch") or self._files.current_branch()
        return web.json_response(await self._run(self._files.remote(branch)))

    async def _diff(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        commit = request.match_info["commit"]
        if not COMMIT.match(commit):
            raise web.HTTPBadRequest(text="not a commit id")
        return web.json_response({"diff": await self._run(self._files.diff(commit))})

    async def _write(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, FileWriteRequest)
        commit = await self._run(
            self._files.write(body.branch, body.path, body.text, body.base, body.message)
        )
        blob = None
        if body.text is not None:
            blob = (await self._run(self._files.read(body.branch, body.path)))["blob"]
        return web.json_response({"commit": commit, "blob": blob})

    @staticmethod
    async def _run(work):  # type: ignore[no-untyped-def]
        try:
            return await work
        except RepositoryConflict as exc:
            raise web.HTTPConflict(text=str(exc)) from exc
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
