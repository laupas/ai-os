import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.agents.catalog_error import CatalogError
from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.engine.claude_credentials import VARIABLES
from aios.entities.users.permission import Permission
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.claude_settings_request import ClaudeSettingsRequest
from aios.web.claude_sign_in_check import ClaudeSignInCheck
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

DESCRIPTION = {
    "subscription": "Claude Code token (claude setup-token), set in Settings",
    "api_key": "Anthropic API key, set in Settings",
}


class ClaudeSettingsRoutes(WebRoutes):
    """How ai-os signs in to Claude, without editing aios.yaml by hand.
    Administrators only.

    The choice is `agent.auth` in aios.yaml, written in place (comments kept) and,
    with a configuration repository, committed; it applies after a restart. The
    token or key is a secret Variable of the name `ClaudeCredentials` reads, so a
    new one applies to the next turn. Neither value is ever sent back. A check
    tries one before it is saved, or the stored one.
    """

    def __init__(
        self,
        config: AiosYamlFile,
        variables: VariableCatalog,
        resolver: VariableResolver,
        running_auth: str,
        sign_in_check: ClaudeSignInCheck | None = None,
    ) -> None:
        self._config = config
        self._variables = variables
        self._resolver = resolver
        self._running_auth = running_auth
        self._editor = ConfigYamlEditor()
        self._sign_in_check = sign_in_check

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings/claude", self._read)
        app.router.add_put("/api/settings/claude", self._save)
        app.router.add_post("/api/settings/claude/check", self._check)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._state())

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ClaudeSettingsRequest)
        value = (body.value or "").strip()
        if value:
            variable = VARIABLES[body.auth]
            try:
                await self._variables.save(
                    variable, value, True, False, DESCRIPTION[body.auth], caller.user.name
                )
            except CatalogError as exc:
                raise web.HTTPBadRequest(text=str(exc)) from exc
            self._resolver.forget(variable)
        if body.auth != self._configured_auth():
            text = self._editor.set(self._config.read(), ["agent", "auth"], body.auth)
            try:
                AppConfig.model_validate(yaml.safe_load(text) or {})
            except (yaml.YAMLError, ValidationError) as exc:
                raise web.HTTPBadRequest(text=str(exc)) from exc
            await self._config.write(text, f"aios.yaml: sign in to Claude with {body.auth}")
        return web.json_response(self._state())

    async def _check(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ClaudeSettingsRequest)
        if self._sign_in_check is None:
            raise web.HTTPNotImplemented(text="checking the sign-in is not available here")
        result = await self._sign_in_check.check(body.auth, (body.value or "").strip() or None)
        return web.json_response(result.model_dump())

    def _state(self) -> dict:
        return {
            "auth": self._configured_auth(),
            "running_auth": self._running_auth,
            "credentials": {
                auth: {"variable": name, "source": self._resolver.source_of(name)}
                for auth, name in VARIABLES.items()
            },
        }

    def _configured_auth(self) -> str:
        """What aios.yaml says now, which may not yet be what is running; what is
        running when the file does not parse."""
        try:
            return AppConfig.model_validate(yaml.safe_load(self._config.read()) or {}).agent.auth
        except (yaml.YAMLError, ValidationError):
            return self._running_auth
