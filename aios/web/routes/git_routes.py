from aiohttp import web

from aios.config_repo.branch_error import BranchError
from aios.config_repo.config_branches import ConfigBranches
from aios.config_repo.config_remote import ConfigRemote
from aios.config_repo.remote_result import RemoteResult
from aios.entities.users.permission import Permission
from aios.web.branch_request import BranchRequest
from aios.web.delete_branch_request import DeleteBranchRequest
from aios.web.merge_request import MergeRequest
from aios.web.pull_request import PullRequest
from aios.web.push_request import PushRequest
from aios.web.remote_request import RemoteRequest
from aios.web.request_body import RequestBody
from aios.web.switch_request import SwitchRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class GitRoutes(WebRoutes):
    """Branches of the configuration repository: list, create, switch, merge,
    compare, delete. Administrators only. Branch names travel in the body or the
    query, since they may contain a slash."""

    def __init__(self, branches: ConfigBranches, remote: ConfigRemote | None = None) -> None:
        self._branches = branches
        self._remote = remote

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/git", self._overview)
        app.router.add_get("/api/git/compare", self._compare)
        app.router.add_post("/api/git/branches", self._create)
        app.router.add_post("/api/git/switch", self._switch)
        app.router.add_post("/api/git/merge", self._merge)
        app.router.add_post("/api/git/delete", self._delete)
        app.router.add_get("/api/git/remote", self._remote_read)
        app.router.add_put("/api/git/remote", self._remote_save)
        app.router.add_delete("/api/git/remote", self._remote_remove)
        app.router.add_post("/api/git/remote/key", self._remote_key)
        app.router.add_post("/api/git/remote/test", self._remote_test)
        app.router.add_post("/api/git/fetch", self._fetch)
        app.router.add_post("/api/git/push", self._push)
        app.router.add_post("/api/git/pull", self._pull)

    async def _overview(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(await self._branches.overview())

    async def _compare(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(
            await self._run(self._branches.compare(request.query.get("branch", "")))
        )

    async def _create(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, BranchRequest)
        await self._run(self._branches.create(body.name, body.start))
        return web.json_response({"ok": True}, status=201)

    async def _switch(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, SwitchRequest)
        await self._run(self._branches.switch(body.branch))
        return web.json_response({"ok": True})

    async def _merge(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, MergeRequest)
        conflicts = await self._run(self._branches.merge(body.source, body.into))
        if conflicts:
            return web.json_response({"merged": False, "conflicts": conflicts}, status=409)
        return web.json_response({"merged": True, "conflicts": []})

    async def _delete(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, DeleteBranchRequest)
        await self._run(self._branches.delete(body.branch, body.force))
        return web.json_response({"ok": True})

    async def _remote_read(self, request: web.Request) -> web.Response:
        """Never the key or the token: only whether they are set."""
        WebAuth.caller(request, Permission.ADMINISTER)
        remote = self._need_remote()
        settings = remote.settings()
        return web.json_response(
            {
                "url": settings.url if settings else "",
                "auth": settings.auth if settings else "ssh",
                "public_key": settings.public_key if settings else None,
                "has_token": bool(settings and settings.token),
                "auto_push": bool(settings and settings.auto_push),
                "updated_by": settings.updated_by if settings else None,
                "last": remote.last.model_dump(mode="json") if remote.last else None,
                "branches": remote.branch_status() if settings and settings.url else {},
            }
        )

    async def _remote_save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, RemoteRequest)
        await self._run(
            self._need_remote().save(
                body.url, body.auth, body.token, body.auto_push, caller.user.name
            )
        )
        return web.json_response({"ok": True})

    async def _remote_remove(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        await self._need_remote().remove()
        return web.json_response({"ok": True})

    async def _remote_key(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        public = await self._need_remote().generate_key(caller.user.name)
        return web.json_response({"public_key": public})

    async def _remote_test(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return self._result(await self._run(self._need_remote().test()))

    async def _fetch(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return self._result(await self._run(self._need_remote().fetch()))

    async def _push(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, PushRequest)
        return self._result(await self._run(self._need_remote().push(body.branch)))

    async def _pull(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, PullRequest)
        conflicts = await self._run(self._need_remote().pull(body.branch))
        if conflicts:
            return web.json_response({"merged": False, "conflicts": conflicts}, status=409)
        return web.json_response({"merged": True, "conflicts": []})

    def _need_remote(self) -> ConfigRemote:
        if self._remote is None:
            raise web.HTTPServiceUnavailable(text="no remote support here")
        return self._remote

    @staticmethod
    def _result(result: RemoteResult) -> web.Response:
        return web.json_response(result.model_dump(mode="json"), status=200 if result.ok else 502)

    @staticmethod
    async def _run(operation):  # type: ignore[no-untyped-def]
        try:
            return await operation
        except BranchError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
