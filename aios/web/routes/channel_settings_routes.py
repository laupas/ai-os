import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.agents.catalog_error import CatalogError
from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_catalog import ChannelCatalog
from aios.channels.channel_type import ChannelType
from aios.channels.channel_values import ChannelValues
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.entities.users.permission import Permission
from aios.variables.variable_catalog import VariableCatalog
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.channel_settings_request import ChannelSettingsRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class ChannelSettingsRoutes(WebRoutes):
    """The channels, without editing aios.yaml or .env by hand. Administrators only.

    On or off is `channels` in aios.yaml (a commit); the values are Variables, a
    secret one encrypted and never sent back, with the environment as fallback.
    Both apply after a restart. A check tries the values, typed or stored, without
    sending anything.
    """

    def __init__(
        self,
        config: AiosYamlFile,
        catalog: ChannelCatalog,
        values: ChannelValues,
        variables: VariableCatalog,
        running: list[str],
    ) -> None:
        self._config = config
        self._catalog = catalog
        self._values = values
        self._variables = variables
        self._running = set(running)
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings/channels", self._read)
        app.router.add_put("/api/settings/channels/{name}", self._save)
        app.router.add_post("/api/settings/channels/{name}/check", self._check)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._state())

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        channel = self._channel(request)
        body = await RequestBody.parse(request, ChannelSettingsRequest)
        fields = {f.variable: f for f in channel.fields}
        unknown = sorted(set(body.values) - set(fields))
        if unknown:
            raise web.HTTPBadRequest(text=f"{channel.title} has no {', '.join(unknown)}")
        given = {k: v.strip() for k, v in body.values.items() if v.strip()}
        if body.enabled is not None:
            self._check_switch(channel, body.enabled, given)
        for variable, value in given.items():
            field = fields[variable]
            try:
                await self._variables.save(
                    variable,
                    value,
                    field.secret,
                    False,
                    f"{channel.title}: {field.label}",
                    caller.user.name,
                )
            except CatalogError as exc:
                raise web.HTTPBadRequest(text=str(exc)) from exc
        if body.enabled is not None and body.enabled != (channel.name in self._configured()):
            await self._switch(channel, body.enabled)
        return web.json_response(self._state())

    async def _check(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        channel = self._channel(request)
        body = await RequestBody.parse(request, ChannelSettingsRequest)
        typed = {k: v.strip() for k, v in body.values.items() if v.strip()}
        result = await channel.check(self._values.of(channel, typed))
        if result is None:
            raise web.HTTPNotFound(text=f"{channel.title} has no test")
        return web.json_response(result.model_dump())

    def _check_switch(self, channel: ChannelType, on: bool, given: dict[str, str]) -> None:
        """Refuses what would keep ai-os from starting, or leave it no way to talk."""
        if on and ChannelCapability.CHAT in channel.capabilities:
            values = self._values.of(channel, given)
            missing = [f.label for f in channel.fields if f.required and not values[f.variable]]
            if missing:
                raise web.HTTPBadRequest(
                    text=f"{channel.title} would not start without: {', '.join(missing)}"
                )
        if not on and ChannelCapability.CHAT in channel.capabilities:
            others = [self._catalog.get(n) for n in self._configured() if n != channel.name]
            if not any(t and ChannelCapability.CHAT in t.capabilities for t in others):
                raise web.HTTPConflict(text="ai-os needs at least one channel to chat on")

    async def _switch(self, channel: ChannelType, on: bool) -> None:
        current = self._parsed()
        channels = {
            name: {"enabled": c.enabled}
            for name, c in (current.channels if current else {}).items()
        }
        channels[channel.name] = {"enabled": on}
        text = self._editor.replace_section(self._config.read(), "channels", channels)
        # The older second list is in `channels` now.
        text = self._editor.replace_section(text, "senders", None)
        try:
            AppConfig.model_validate(yaml.safe_load(text) or {})
        except (yaml.YAMLError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        verb = "on" if on else "off"
        await self._config.write(text, f"aios.yaml: {channel.name} {verb}")

    def _state(self) -> dict:
        configured = self._configured()
        return {
            "channels": [
                {
                    "name": t.name,
                    "title": t.title,
                    "description": t.description,
                    "capabilities": sorted(c.value for c in t.capabilities),
                    "enabled": t.name in configured,
                    "running": t.name in self._running,
                    "checkable": type(t).check is not ChannelType.check,
                    "fields": [self._values.row(f) for f in t.fields],
                    "setup": [s.model_dump() for s in t.setup],
                    "problems": [p.model_dump() for p in t.problems],
                }
                for t in self._catalog.all()
            ]
        }

    def _configured(self) -> list[str]:
        parsed = self._parsed()
        return parsed.enabled_channels() if parsed else sorted(self._running)

    def _parsed(self) -> AppConfig | None:
        try:
            return AppConfig.model_validate(yaml.safe_load(self._config.read()) or {})
        except (yaml.YAMLError, ValidationError):
            return None

    def _channel(self, request: web.Request) -> ChannelType:
        channel = self._catalog.get(request.match_info["name"])
        if channel is None:
            raise web.HTTPNotFound(text="no such channel")
        return channel
