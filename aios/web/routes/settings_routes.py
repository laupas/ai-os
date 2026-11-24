import asyncio
import json
import re

import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.common.id_generator import IdGenerator
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config.live_app_config import LiveAppConfig
from aios.entities.users.audience_entry import EVERYONE
from aios.entities.users.group import Group
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.config_insert_request import ConfigInsertRequest
from aios.web.login.web_sessions import WebSessions
from aios.web.request_body import RequestBody
from aios.web.restart_request import RestartRequest
from aios.web.text_request import TextRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

RESTART_DELAY_SECONDS = 0.5
GROUP_ID = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
GROUP_ID_CHARS = re.compile(r"[^a-z0-9_-]+")


class SettingsRoutes(WebRoutes):
    """aios.yaml, users and groups, and the restart that applies what needs one.

    Administrators only. Every save is validated against the same model ai-os reads
    it with, so a typo is refused here rather than found at the next start. Users
    and groups take effect at once, and so does aios.yaml within seconds, except
    the sections read only at startup (`LiveAppConfig`). With a configuration
    repository, aios.yaml lives there and every save is a commit; a branch switch
    can change it too, so "restart needed" compares the file with what this
    process started from, whoever changed it.
    """

    def __init__(
        self,
        config: AiosYamlFile,
        live: LiveAppConfig,
        users: Collection[User],
        groups: Collection[Group],
        ids: IdGenerator,
        restart: RestartRequest,
        sessions: WebSessions | None = None,
    ) -> None:
        self._sessions = sessions
        self._config = config
        self._live = live
        self._users = users
        self._groups = groups
        self._ids = ids
        self._restart = restart
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings", self._read)
        app.router.add_put("/api/settings/config", self._save_config)
        app.router.add_post("/api/settings/config-insert", self._insert)
        app.router.add_post("/api/settings/users", self._create_user)
        app.router.add_put("/api/settings/users/{id}", self._save_user)
        app.router.add_delete("/api/settings/users/{id}", self._delete_user)
        app.router.add_post("/api/settings/groups", self._create_group)
        app.router.add_put("/api/settings/groups/{id}", self._save_group)
        app.router.add_delete("/api/settings/groups/{id}", self._delete_group)
        app.router.add_post("/api/restart", self._request_restart)
        app.router.add_get("/api/restart-needed", self._restart_needed)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        text = self._config.read()
        return web.json_response(
            {
                "config": text,
                "config_schema": AppConfig.model_json_schema(),
                "restart_needed": self._live.restart_needed(text),
                "in_repository": self._config.in_repository(),
                "users": [u.model_dump(mode="json") for u in self._users.all()],
                "groups": [g.model_dump(mode="json") for g in self._groups.all()],
                "permissions": [p.value for p in Permission],
                "permission_descriptions": {p.value: p.description for p in Permission},
            }
        )

    async def _save_config(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, TextRequest)
        try:
            AppConfig.model_validate(yaml.safe_load(body.text) or {})
        except (yaml.YAMLError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return await self._write_config(body.text)

    async def _insert(self, request: web.Request) -> web.Response:
        """A key from the reference written into the text being edited, which is
        not saved: the editor shows it, and Save is still the editor's."""
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ConfigInsertRequest)
        try:
            return web.json_response(
                {"text": self._editor.insert(body.text, body.path, body.value)}
            )
        except Exception as exc:  # noqa: BLE001 - text that does not parse cannot take a key
            raise web.HTTPBadRequest(text=f"aios.yaml does not parse: {exc}") from exc

    async def _write_config(self, text: str) -> web.Response:
        await self._config.write(text)
        return web.json_response({"ok": True, "restart_needed": self._live.restart_needed(text)})

    async def _restart_needed(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response({"restart_needed": self._live.restart_needed(self._config.read())})

    async def _create_user(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        user = self._document(await RequestBody.parse(request, TextRequest), User)
        user = user.model_copy(update={"id": self._ids.new_id(), "role_ids": []})
        self._check_user(user)
        await self._users.put(user)
        return web.json_response(user.model_dump(mode="json"), status=201)

    async def _save_user(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        user_id = request.match_info["id"]
        if self._users.get(user_id) is None:
            raise web.HTTPNotFound(text="no such user")
        user = self._document(await RequestBody.parse(request, TextRequest), User)
        user = user.model_copy(update={"id": user_id, "role_ids": []})
        self._check_user(user)
        self._keep_an_administrator(users={user_id: user})
        await self._users.put(user)
        return web.json_response({"ok": True})

    async def _delete_user(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        user_id = request.match_info["id"]
        if user_id == caller.user.id:
            raise web.HTTPConflict(text="you cannot delete yourself")
        if self._users.get(user_id) is None:
            raise web.HTTPNotFound(text="no such user")
        await self._users.delete(user_id)
        if self._sessions is not None:
            await self._sessions.end_all(user_id)
        return web.json_response({"ok": True})

    async def _create_group(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        group = self._document(await RequestBody.parse(request, TextRequest), Group)
        group_id = (
            group.id if group.id != "new" else GROUP_ID_CHARS.sub("_", group.name.strip().lower())
        )
        if not GROUP_ID.match(group_id):
            raise web.HTTPBadRequest(text="a group id is lower-case letters, digits, _ and -")
        if group_id == EVERYONE:
            raise web.HTTPConflict(text="everyone is built in: everybody is in it")
        if self._groups.get(group_id) is not None:
            raise web.HTTPConflict(text=f"there is already a group {group_id}")
        group = group.model_copy(update={"id": group_id, "role_ids": []})
        await self._groups.put(group)
        return web.json_response(group.model_dump(mode="json"), status=201)

    async def _save_group(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        group_id = request.match_info["id"]
        if self._groups.get(group_id) is None:
            raise web.HTTPNotFound(text="no such group")
        group = self._document(await RequestBody.parse(request, TextRequest), Group)
        group = group.model_copy(update={"id": group_id, "role_ids": []})
        self._keep_an_administrator(groups={group_id: group})
        await self._groups.put(group)
        return web.json_response({"ok": True})

    async def _delete_group(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        group_id = request.match_info["id"]
        if self._groups.get(group_id) is None:
            raise web.HTTPNotFound(text="no such group")
        members = [u.name for u in self._users.all() if group_id in u.group_ids]
        if members:
            raise web.HTTPConflict(text=f"{', '.join(members)} still in it; take them out first")
        await self._groups.delete(group_id)
        return web.json_response({"ok": True})

    def _check_user(self, user: User) -> None:
        unknown = [g for g in user.group_ids if self._groups.get(g) is None]
        if unknown:
            raise web.HTTPBadRequest(text=f"no such group: {', '.join(unknown)}")

    def _keep_an_administrator(
        self, users: dict[str, User] | None = None, groups: dict[str, Group] | None = None
    ) -> None:
        """Refuses a change after which nobody could administer ai-os any more:
        that would lock everyone out of the console that could undo it."""
        all_groups = {g.id: g for g in self._groups.all()} | (groups or {})
        all_users = {u.id: u for u in self._users.all()} | (users or {})
        for user in all_users.values():
            for group_id in user.group_ids:
                group = all_groups.get(group_id)
                if group is not None and Permission.ADMINISTER in group.permissions:
                    return
        raise web.HTTPConflict(text="nobody could administer ai-os after this; keep at least one")

    async def _request_restart(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        # Later, so this response still goes out before the server stops.
        asyncio.get_running_loop().call_later(RESTART_DELAY_SECONDS, self._restart.request)
        return web.json_response({"ok": True}, status=202)

    @staticmethod
    def _document[M: (User, Group)](body: TextRequest, model: type[M]) -> M:
        try:
            data = json.loads(body.text)
            if isinstance(data, dict):
                data.setdefault("id", "new")
            return model.model_validate(data)
        except (ValueError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
