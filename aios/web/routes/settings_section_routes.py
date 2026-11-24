from typing import Any

import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.entities.users.permission import Permission
from aios.storage.collection_access_overrides import CollectionAccessOverrides
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.request_body import RequestBody
from aios.web.section_request import SectionRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

EDITABLE = ["timezone", "triggers", "agent", "approval", "collection_access", "api_docs"]
"""The sections the console's generic forms edit. `web`, `files` and `channels` have
routes of their own, with their own checks; the rest stays on the aios.yaml tab."""


class SettingsSectionRoutes(WebRoutes):
    """aios.yaml one section at a time, for the console's forms. Administrators only.

    A save changes only that section, keeps the comments of what stays, is checked
    against the model ai-os reads the file with, and is a commit like any other
    save of aios.yaml. It applies within seconds, `collection_access` after a restart.
    """

    def __init__(
        self, config: AiosYamlFile, collections: CollectionAccessOverrides | None = None
    ) -> None:
        self._config = config
        self._collections = collections
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings/sections", self._read)
        app.router.add_put("/api/settings/sections/{key}", self._save)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        schema = AppConfig.model_json_schema()
        values = self._values()
        return web.json_response(
            {
                "sections": {
                    key: {
                        "schema": {**schema["properties"][key], "$defs": schema.get("$defs", {})},
                        "value": values.get(key),
                    }
                    for key in EDITABLE
                },
                # Only these collections' agent access can be changed, and from what.
                "collections": {name: access.value for name, access in self._defaults().items()},
            }
        )

    async def _save(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        key = request.match_info["key"]
        if key not in EDITABLE:
            raise web.HTTPNotFound(text=f"{key} is edited on the aios.yaml tab")
        body = await RequestBody.parse(request, SectionRequest)
        if key == "collection_access" and isinstance(body.value, dict):
            fixed = sorted(set(body.value) - set(self._defaults()))
            if fixed:
                raise web.HTTPBadRequest(text=f"agent access is fixed for {', '.join(fixed)}")
        try:
            text = self._editor.replace_section(self._config.read(), key, body.value)
            AppConfig.model_validate(yaml.safe_load(text) or {})
        except (yaml.YAMLError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=self._message(exc)) from exc
        await self._config.write(text, f"aios.yaml: {key}")
        return web.json_response({"value": self._values().get(key)})

    def _defaults(self) -> dict:
        return self._collections.defaults() if self._collections else {}

    def _values(self) -> dict[str, Any]:
        try:
            loaded = yaml.safe_load(self._config.read()) or {}
        except yaml.YAMLError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _message(exc: Exception) -> str:
        """Pydantic's errors without the URL lines, which say nothing in the console."""
        if isinstance(exc, ValidationError):
            return "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg'].removeprefix('Value error, ')}"
                for e in exc.errors()
            )
        return str(exc)
