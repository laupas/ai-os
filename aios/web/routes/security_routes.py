from aiohttp import web

from aios.entities.users.permission import Permission
from aios.variables.secret_box import SecretBox
from aios.variables.secrets_key_rotation import SecretsKeyRotation
from aios.variables.secrets_key_source import SecretsKeySource
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes


class SecurityRoutes(WebRoutes):
    """Settings → Security, for administrators: the secrets key in use (by its
    fingerprint, never the key) and how many secrets it opens; a new key to put into
    `AIOS_SECRETS_KEY`; and, while an older ai-os's key file is in the data dir, that
    key, so it can be moved into the setting. ai-os never stores a key it hands out
    here: a key takes effect only from the setting, at the next start. Both are
    recorded in the audit trail (`AuditMiddleware`)."""

    def __init__(self, rotation: SecretsKeyRotation, source: SecretsKeySource) -> None:
        self._rotation = rotation
        self._source = source

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/security", self._status)
        app.router.add_post("/api/security/keys", self._new_key)
        app.router.add_post("/api/security/data-dir-key", self._data_dir_key)

    async def _status(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        return web.json_response(self._rotation.status().model_dump(mode="json"))

    async def _new_key(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        key = SecretBox.new_key()
        return web.json_response({"key": key, "fingerprint": SecretBox.fingerprint_of(key)})

    async def _data_dir_key(self, request: web.Request) -> web.Response:
        WebAuth.caller(request, Permission.ADMINISTER)
        key = self._source.legacy_key()
        if key is None:
            raise web.HTTPNotFound(text="there is no key file in the data dir")
        return web.json_response({"key": key, "fingerprint": SecretBox.fingerprint_of(key)})
