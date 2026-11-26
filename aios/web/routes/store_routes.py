import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.agents.agent_catalog import AgentCatalog
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config.store_source import StoreSource
from aios.entities.users.permission import Permission
from aios.store.store_connector_copy import StoreConnectorCopy
from aios.store.store_error import StoreError
from aios.store.store_installer import StoreInstaller
from aios.store.store_item import StoreItem
from aios.store.store_kind import StoreKind
from aios.store.store_listing import StoreListing
from aios.store.store_ref import StoreRef
from aios.store.store_sources import StoreSources
from aios.store.store_version import StoreVersion
from aios.variables.variable_field_state import VariableFieldState
from aios.variables.variable_resolver import VariableResolver
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.request_body import RequestBody
from aios.web.store_install_request import StoreInstallRequest
from aios.web.store_source_request import StoreSourceRequest
from aios.web.store_uninstall_request import StoreUninstallRequest
from aios.web.store_update_request import StoreUpdateRequest
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class StoreRoutes(WebRoutes):
    """The Store: what the sources in aios.yaml offer, installed one item at a time.
    Administrators only, except the installed versions, which the pages of agents,
    skills and connectors show. Adding or removing a source is a save of aios.yaml."""

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
        app.router.add_get("/api/store/installed", self._installed)
        app.router.add_post("/api/store/refresh", self._refresh)
        app.router.add_post("/api/store/sources", self._add_source)
        app.router.add_delete("/api/store/sources", self._remove_source)
        app.router.add_post("/api/store/install", self._install)
        app.router.add_post("/api/store/update", self._update)
        app.router.add_post("/api/store/uninstall", self._uninstall)

    async def _list(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._state(await self._sources.listings()))

    async def _installed(self, request: web.Request) -> web.Response:
        """The version of each item installed from the Store, for the pages of
        agents, skills and connectors; `latest` only when a source last fetched
        offers a newer one."""
        WebAuth.caller_any(
            request,
            Permission.MANAGE_AGENTS,
            Permission.MANAGE_SKILLS,
            Permission.MANAGE_CONNECTORS,
        )
        listings = {s.url: s for s in await self._sources.fetched()}
        rows = {}
        for ref, record in self._installer.records().items():
            listing = listings.get(record.source)
            offered_as = StoreRef(kind=ref.kind, id=record.copy_of or ref.id)
            offered = listing.get(offered_as) if listing else None
            latest = offered.meta.version if offered else None
            rows[str(ref)] = {
                "version": record.version,
                "source": record.source,
                "installed_at": record.installed_at.isoformat(),
                "installed_by": record.installed_by,
                "copy_of": record.copy_of,
                "latest": latest if StoreVersion.newer(latest, record.version) else None,
                "code": bool(offered and offered.code_folder is not None),
            }
        return web.json_response(rows)

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
        values = body.variables
        try:
            if body.name and body.name != item.id:
                original, item = item, StoreConnectorCopy.of(item, body.name)
                names = dict(
                    zip(
                        (v.variable for v in original.meta.variables),
                        (v.variable for v in item.meta.variables),
                        strict=True,
                    )
                )
                values = {names.get(k, k): v for k, v in values.items()}
            plan = self._installer.plan(listing, item)
            result = await self._installer.install(
                plan, caller.user, values, body.replace, body.trust_code
            )
        except StoreError as exc:
            status = web.HTTPConflict if exc.conflict else web.HTTPBadRequest
            raise status(text=str(exc)) from exc
        return web.json_response(result.model_dump())

    async def _update(self, request: web.Request) -> web.Response:
        """Replaces one installed item with what its source offers now, by the id it
        has here: what a page of agents, skills or connectors offers as Update."""
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, StoreUpdateRequest)
        ref = StoreRef(kind=body.kind, id=body.id)
        record = self._installer.records().get(ref)
        if record is None:
            raise web.HTTPNotFound(
                text=f"{body.kind.value} {body.id} was not installed from the Store"
            )
        offered = StoreRef(kind=body.kind, id=record.copy_of or body.id)
        found = await self._sources.find(record.source, offered)
        if found is None:
            raise web.HTTPNotFound(
                text=f"its source offers no {offered.kind.value} {offered.id} any more"
            )
        listing, item = found
        try:
            if record.copy_of:
                item = StoreConnectorCopy.of(item, body.id)
            plan = self._installer.plan(listing, item)
            result = await self._installer.install(
                plan, caller.user, {}, replace=True, trust_code=body.trust_code
            )
        except StoreError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
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
            "copies": self._installer.copies(item),
            # Its own, which a copy reads under names of its own (`StoreConnectorCopy`).
            "own_variables": [v.variable for v in item.meta.variables],
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
