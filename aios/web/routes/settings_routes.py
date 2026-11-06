import asyncio
import json
import re
from pathlib import Path

import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.common.id_generator import IdGenerator
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config.settings import CONFIG_FILE_NAME
from aios.config_repo.git_document_store import GitDocumentStore
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.web.config_values_request import ConfigValuesRequest
from aios.web.request_body import RequestBody
from aios.web.restart_request import RestartRequest
from aios.web.text_request import TextRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

RESTART_DELAY_SECONDS = 0.5
ROLE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
ROLE_ID_CHARS = re.compile(r"[^a-z0-9_-]+")


class SettingsRoutes(WebRoutes):
    """aios.yaml, users and roles, and the restart that applies them.

    Administrators only. Every save is validated against the same model ai-os reads
    it with, so a typo is refused here rather than found at the next start. Users
    and roles take effect at once; aios.yaml at the next restart. With a
    configuration repository, aios.yaml lives there and every save is a commit; a
    branch switch can change it too, so "restart needed" compares the file with
    what this process started from, whoever changed it.
    """

    def __init__(
        self,
        config_file: Path,
        users: Collection[User],
        roles: Collection[Role],
        ids: IdGenerator,
        restart: RestartRequest,
        store: GitDocumentStore | None = None,
    ) -> None:
        self._config_file = Path(config_file)
        self._store = store
        # What this process was started with: the reference for "restart needed".
        self._started_with = self._current_text()
        self._users = users
        self._roles = roles
        self._ids = ids
        self._restart = restart
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings", self._read)
        app.router.add_put("/api/settings/config", self._save_config)
        app.router.add_put("/api/settings/config-values", self._save_config_values)
        app.router.add_post("/api/settings/users", self._create_user)
        app.router.add_put("/api/settings/users/{id}", self._save_user)
        app.router.add_delete("/api/settings/users/{id}", self._delete_user)
        app.router.add_put("/api/settings/roles/{id}", self._save_role)
        app.router.add_post("/api/settings/roles", self._create_role)
        app.router.add_delete("/api/settings/roles/{id}", self._delete_role)
        app.router.add_post("/api/restart", self._request_restart)
        app.router.add_get("/api/restart-needed", self._restart_needed)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        text = self._current_text()
        return web.json_response(
            {
                "config": text,
                "config_values": self._values(text),
                "config_schema": AppConfig.model_json_schema(),
                "restart_needed": text != self._started_with,
                "in_repository": self._in_repository(),
                "users": [u.model_dump(mode="json") for u in self._users.all()],
                "roles": [r.model_dump(mode="json") for r in self._roles.all()],
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

    async def _save_config_values(self, request: web.Request) -> web.Response:
        """The form's save: the values go into the file as it is, so its comments
        and everything the form does not show survive."""
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ConfigValuesRequest)
        try:
            AppConfig.model_validate(body.values)
        except ValidationError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return await self._write_config(self._editor.apply(self._current_text(), body.values))

    async def _write_config(self, text: str) -> web.Response:
        if self._in_repository():
            await self._store.write_file(CONFIG_FILE_NAME, text, f"{CONFIG_FILE_NAME}: update")  # type: ignore[union-attr]
        else:
            await asyncio.to_thread(self._config_file.write_text, text, "utf-8")
        return web.json_response({"ok": True, "restart_needed": text != self._started_with})

    def _values(self, text: str) -> dict | None:
        """None when the file does not parse; the form then has nothing to show."""
        try:
            return self._editor.values(text)
        except Exception:  # noqa: BLE001 - any parse failure means "use the YAML tab"
            return None

    async def _restart_needed(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response({"restart_needed": self._current_text() != self._started_with})

    def _in_repository(self) -> bool:
        return self._store is not None and self._store.repo.exists()

    def _current_text(self) -> str:
        if self._in_repository():
            return self._store.read_file(CONFIG_FILE_NAME) or ""  # type: ignore[union-attr]
        return self._config_file.read_text("utf-8") if self._config_file.exists() else ""

    async def _create_user(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        user = self._document(await RequestBody.parse(request, TextRequest), User)
        user = user.model_copy(update={"id": self._ids.new_id()})
        self._check_user(user)
        await self._users.put(user)
        return web.json_response(user.model_dump(mode="json"), status=201)

    async def _save_user(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        user_id = request.match_info["id"]
        if self._users.get(user_id) is None:
            raise web.HTTPNotFound(text="no such user")
        user = self._document(await RequestBody.parse(request, TextRequest), User)
        user = user.model_copy(update={"id": user_id})
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
        return web.json_response({"ok": True})

    async def _save_role(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        role_id = request.match_info["id"]
        if self._roles.get(role_id) is None:
            raise web.HTTPNotFound(text="no such role")
        role = self._document(await RequestBody.parse(request, TextRequest), Role)
        role = role.model_copy(update={"id": role_id})
        self._keep_an_administrator(roles={role_id: role})
        await self._roles.put(role)
        return web.json_response({"ok": True})

    async def _create_role(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        role = self._document(await RequestBody.parse(request, TextRequest), Role)
        role_id = role.id if role.id != "new" else ROLE_ID_CHARS.sub("_", role.name.strip().lower())
        if not ROLE_ID.match(role_id):
            raise web.HTTPBadRequest(text="a role id is lower-case letters, digits, _ and -")
        if self._roles.get(role_id) is not None:
            raise web.HTTPConflict(text=f"there is already a role {role_id}")
        role = role.model_copy(update={"id": role_id})
        await self._roles.put(role)
        return web.json_response(role.model_dump(mode="json"), status=201)

    async def _delete_role(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        role_id = request.match_info["id"]
        if self._roles.get(role_id) is None:
            raise web.HTTPNotFound(text="no such role")
        holders = [u.name for u in self._users.all() if role_id in u.role_ids]
        if holders:
            raise web.HTTPConflict(text=f"still given to {', '.join(holders)}; take it away first")
        await self._roles.delete(role_id)
        return web.json_response({"ok": True})

    def _check_user(self, user: User) -> None:
        unknown = [r for r in user.role_ids if self._roles.get(r) is None]
        if unknown:
            raise web.HTTPBadRequest(text=f"no such role: {', '.join(unknown)}")

    def _keep_an_administrator(
        self, users: dict[str, User] | None = None, roles: dict[str, Role] | None = None
    ) -> None:
        """Refuses a change after which nobody could administer ai-os any more:
        that would lock everyone out of the console that could undo it."""
        all_roles = {r.id: r for r in self._roles.all()} | (roles or {})
        all_users = {u.id: u for u in self._users.all()} | (users or {})
        for user in all_users.values():
            for role_id in user.role_ids:
                role = all_roles.get(role_id)
                if role is not None and Permission.ADMINISTER in role.permissions:
                    return
        raise web.HTTPConflict(text="nobody could administer ai-os after this; keep at least one")

    async def _request_restart(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        # Later, so this response still goes out before the server stops.
        asyncio.get_running_loop().call_later(RESTART_DELAY_SECONDS, self._restart.request)
        return web.json_response({"ok": True}, status=202)

    @staticmethod
    def _document[M: (User, Role)](body: TextRequest, model: type[M]) -> M:
        try:
            data = json.loads(body.text)
            if isinstance(data, dict):
                data.setdefault("id", "new")
            return model.model_validate(data)
        except (ValueError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
