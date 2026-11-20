import aiohttp
from aiohttp import web

from aios.agents.catalog_error import CatalogError
from aios.entities.users.permission import Permission
from aios.transcription.whisper_transcriber import KEY, LANGUAGE
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from aios.web.channel_settings_request import ChannelSettingsRequest
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

MODEL_URL = "https://api.openai.com/v1/models/whisper-1"


class VoiceSettingsRoutes(WebRoutes):
    """Voice notes: the OpenAI key that transcribes them and their language, as
    Variables (the key encrypted), with the environment as fallback. The
    transcriber reads them for every note, so a change needs no restart.
    Administrators only."""

    FIELDS = {KEY: True, LANGUAGE: False}  # variable: secret

    def __init__(self, variables: VariableCatalog, resolver: VariableResolver) -> None:
        self._variables = variables
        self._resolver = resolver

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings/voice", self._read)
        app.router.add_put("/api/settings/voice", self._save)
        app.router.add_post("/api/settings/voice/check", self._check)

    async def _read(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._state())

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ChannelSettingsRequest)
        unknown = sorted(set(body.values) - set(self.FIELDS))
        if unknown:
            raise web.HTTPBadRequest(text=f"voice notes have no {', '.join(unknown)}")
        for name, value in body.values.items():
            if not value.strip():
                continue
            label = "OpenAI key" if name == KEY else "language"
            try:
                await self._variables.save(
                    name,
                    value.strip(),
                    self.FIELDS[name],
                    False,
                    f"Voice notes: {label}",
                    caller.user.name,
                )
            except CatalogError as exc:
                raise web.HTTPBadRequest(text=str(exc)) from exc
        return web.json_response(self._state())

    async def _check(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, ChannelSettingsRequest)
        key = (body.values.get(KEY) or "").strip() or self._resolver.value_of(KEY)
        if not key:
            return web.json_response({"ok": False, "detail": "no key is set"})
        try:
            headers = {"Authorization": f"Bearer {key}"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(MODEL_URL) as response:
                    status = response.status
        except aiohttp.ClientError as exc:
            return web.json_response({"ok": False, "detail": f"OpenAI unreachable: {exc}"})
        if status >= 300:
            return web.json_response({"ok": False, "detail": f"OpenAI refused the key ({status})"})
        return web.json_response({"ok": True, "detail": "key accepted, whisper-1 available"})

    def _state(self) -> dict:
        return {
            "fields": [
                {
                    "variable": name,
                    "secret": secret,
                    "source": self._resolver.source_of(name),
                    "value": None if secret else self._resolver.value_of(name),
                }
                for name, secret in self.FIELDS.items()
            ]
        }
