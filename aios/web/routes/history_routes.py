import asyncio
from typing import Any

from aiohttp import web
from pydantic import ValidationError

from aios.config_repo.git_document_store import GitDocumentStore
from aios.entities.users.permission import Permission
from aios.storage.collection import Collection
from aios.web.request_body import RequestBody
from aios.web.restore_request import RestoreRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class HistoryRoutes(WebRoutes):
    """The git history of one agent, skill, connector or schedule: its commits, what
    each changed, and bringing an earlier version back. Administrators only.

    A restore is a new commit with the old content, never a rewrite of history, and
    goes through the entity model like any save, so a version that no longer
    validates is refused rather than written.
    """

    def __init__(self, store: GitDocumentStore, collections: list[Collection[Any]]) -> None:
        self._store = store
        self._collections = {c.name: c for c in collections}

    def register(self, app: web.Application) -> None:
        base = "/api/history/{collection}/{id}"
        app.router.add_get(base, self._log)
        app.router.add_get(base + "/{commit}", self._diff)
        app.router.add_post(base + "/restore", self._restore)

    async def _log(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        path = self._path(request)
        entries = await asyncio.to_thread(self._store.repo.log, path)
        return web.json_response({"path": path, "commits": entries})

    async def _diff(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        commit = self._commit(request.match_info["commit"])
        diff = await asyncio.to_thread(self._store.repo.diff, commit, self._path(request))
        return web.json_response({"diff": diff})

    async def _restore(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        collection, doc_id = self._collection(request), request.match_info["id"]
        body = await RequestBody.parse(request, RestoreRequest)
        path = self._path(request)
        text = await asyncio.to_thread(self._store.repo.show, body.commit, path)
        if text is None:
            raise web.HTTPNotFound(text="it did not exist in that commit")
        layout = self._store.layout(collection.name)
        try:
            item = collection.parse(layout.parse(text, doc_id))
        except (ValueError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=f"that version no longer loads: {exc}") from exc
        await collection.put(item)
        return web.json_response({"ok": True})

    def _collection(self, request: web.Request) -> Collection[Any]:
        collection = self._collections.get(request.match_info["collection"])
        if collection is None:
            raise web.HTTPNotFound(text="no history for that")
        return collection

    def _path(self, request: web.Request) -> str:
        collection = self._collection(request)
        try:
            return self._store.path_of(collection.name, request.match_info["id"])
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc

    @staticmethod
    def _commit(value: str) -> str:
        try:
            return RestoreRequest(commit=value).commit
        except ValidationError as exc:
            raise web.HTTPBadRequest(text="not a commit id") from exc
