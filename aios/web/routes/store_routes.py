import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.agents.agent_catalog import AgentCatalog
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config.store_source import StoreSource
from aios.entities.users.permission import Permission
from aios.store.store_error import StoreError
from aios.store.store_installer import StoreInstaller
from aios.store.store_item import StoreItem
from aios.store.store_kind import StoreKind
from aios.store.store_listing import StoreListing
from aios.store.store_ref import StoreRef
from aios.store.store_sources import StoreSources
from aios.variables.variable_field_state import VariableFieldState
from aios.variables.variable_resolver import VariableResolver
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.request_body import RequestBody
from aios.web.store_install_request import StoreInstallRequest
from aios.web.store_source_request import StoreSourceRequest
from aios.web.store_uninstall_request import StoreUninstallRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class StoreRoutes(WebRoutes):
    """The Store: what the sources in aios.yaml offer, installed one item at a time.
    Administrators only. Adding or removing a source is a save of aios.yaml."""

    def __init__(
        self,
        sources: StoreSources,
        installer: StoreInstaller,
        config: AiosYamlFile,
        resolver: VariableResolver,
    ) -> None:
        self._sources = sources
        self._installer = installer
        self._config = config
        self._fields = VariableFieldState(resolver)
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/store", self._list)
        app.router.add_post("/api/store/refresh", self._refresh)
        app.router.add_post("/api/store/sources", self._add_source)
        app.router.add_delete("/api/store/sources", self._remove_source)
        app.router.add_post("/api/store/install", self._install)
        app.router.add_post("/api/store/uninstall", self._uninstall)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._state(await self._sources.listings()))

    async def _refresh(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._state(await self._sources.listings(refresh=True)))

    async def _add_source(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, StoreSourceRequest)
        try:
            source = StoreSource(url=body.url, branch=(body.branch or "").strip() or None)
        except ValidationError as exc:
            message = exc.errors()[0]["msg"].removeprefix("Value error, ")
            raise web.HTTPBadRequest(text=message) from exc
        sources = self._configured()
        if any(s.url == source.url for s in sources):
            raise web.HTTPConflict(text="that source is there already")
        await self._save_sources([*sources, source], f"Store: add source {source.url}")
        return web.json_response(self._state(await self._sources.listings()), status=201)

    async def _remove_source(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, StoreSourceRequest)
        sources = self._configured()
        kept = [s for s in sources if s.url != body.url.strip()]
        if len(kept) == len(sources):
            raise web.HTTPNotFound(text="there is no such source")
        await self._save_sources(kept, f"Store: remove source {body.url.strip()}")
        return web.json_response(self._state(await self._sources.listings()))

    async def _install(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, StoreInstallRequest)
        found = await self._sources.find(body.source, StoreRef(kind=body.kind, id=body.id))
        if found is None:
            raise web.HTTPNotFound(text=f"the source offers no {body.kind.value} {body.id}")
        listing, item = found
        plan = self._installer.plan(listing, item)
        try:
            result = await self._installer.install(
                plan, caller.user, body.variables, body.replace, body.trust_code
            )
        except StoreError as exc:
            status = web.HTTPConflict if exc.conflict else web.HTTPBadRequest
            raise status(text=str(exc)) from exc
        return web.json_response(result.model_dump())

    async def _uninstall(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, StoreUninstallRequest)
        try:
            result = await self._installer.uninstall(StoreRef(kind=body.kind, id=body.id))
        except StoreError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return web.json_response(result.model_dump())

    def _fixed(self, item: StoreItem) -> bool:
        return item.kind is StoreKind.AGENT and item.id in AgentCatalog.FIXED

    def _configured(self) -> list[StoreSource]:
        loaded = yaml.safe_load(self._config.read()) or {}
        return AppConfig.model_validate(loaded).store.sources

    async def _save_sources(self, sources: list[StoreSource], message: str) -> None:
        value = {"sources": [s.model_dump(exclude_none=True) for s in sources]}
        text = self._editor.replace_section(self._config.read(), "store", value)
        AppConfig.model_validate(yaml.safe_load(text) or {})
        await self._config.write(text, message)

    def _state(self, listings: list[StoreListing]) -> dict:
        return {
            "sources": [
                {
                    "url": s.url,
                    "branch": s.branch,
                    "name": s.name,
                    "description": s.description,
                    "error": s.error,
                    "problems": s.problems,
                    "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
                }
                for s in listings
            ],
            "items": [self._row(s, i) for s in listings for i in s.items],
        }

    def _row(self, listing: StoreListing, item: StoreItem) -> dict:
        plan = self._installer.plan(listing, item)
        bringing = {i.ref for i in plan.install}
        record = self._installer.record_of(item)
        return {
            "source": listing.url,
            "kind": item.kind.value,
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "category": item.meta.category,
            "notes": item.meta.notes,
            "version": item.meta.version,
            "author": item.meta.author,
            "license": item.meta.license,
            "homepage": item.meta.homepage,
            "tags": item.meta.tags,
            "installed": self._installer.installed(item),
            "installed_version": record.version if record else None,
            "installed_from": record.source if record else None,
            "update_available": self._installer.update_available(item),
            "used_by": self._installer.used_by(item.ref) if self._installer.installed(item) else [],
            "removable": self._installer.installed(item) and not self._fixed(item),
            "code": plan.code,
            "requires": [
                {
                    "kind": ref.kind.value,
                    "id": ref.id,
                    "installed": ref in plan.kept,
                    "in_source": ref in bringing or listing.get(ref) is not None,
                }
                for ref in item.requires()
            ],
            "variables": [self._fields.row(f) for f in plan.variables],
        }
