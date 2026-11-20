from typing import Any

import yaml
from aiohttp import web
from pydantic import ValidationError

from aios.config.app_config import AppConfig
from aios.config.config_yaml_editor import ConfigYamlEditor
from aios.config.web_auth_config import WebAuthConfig
from aios.config.web_config import WebConfig
from aios.entities.users.permission import Permission
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.request_body import RequestBody
from aios.web.web_auth import WebAuth
from aios.web.web_auth_request import WebAuthRequest
from aios.web.web_identity_factory import WebIdentityFactory
from aios.web.web_routes import WebRoutes

OLDER_KEYS = ["access_team_domain", "access_aud", "dev_email"]


class WebAuthSettingsRoutes(WebRoutes):
    """How the console learns who is asking (`web.auth`), without editing aios.yaml.
    Administrators only.

    A wrong setting locks everyone out of the console that could undo it, so a new
    one is first tried on the request that saves it: it is saved only when it would
    recognise this very administrator. `dev` is refused here (it lets anyone in),
    and the console cannot be switched off or moved to another port from here.
    Applies after a restart, like the rest of aios.yaml.
    """

    def __init__(self, config: AiosYamlFile) -> None:
        self._config = config
        self._editor = ConfigYamlEditor()

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/settings/web-auth", self._read)
        app.router.add_post("/api/settings/web-auth/check", self._check)
        app.router.add_put("/api/settings/web-auth", self._save)

    async def _read(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        current = self._web()
        effective = self._effective(current)
        return web.json_response(
            {
                "auth": effective.model_dump() if effective else None,
                "older_form": current.auth is None and bool(current.access_team_domain),
                "public_url": current.public_url,
                "port": current.port,
                "you": caller.account.address,
            }
        )

    async def _check(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, WebAuthRequest)
        return web.json_response(await self._try(request, body.auth, caller.account.address))

    async def _save(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request, Permission.ADMINISTER)
        body = await RequestBody.parse(request, WebAuthRequest)
        if body.auth.mode == "dev":
            raise web.HTTPBadRequest(
                text="dev lets anyone in as one address; set it in aios.yaml, and only on "
                "your own machine"
            )
        tried = await self._try(request, body.auth, caller.account.address)
        if not tried["ok"]:
            raise web.HTTPConflict(text=f"not saved, you would be locked out: {tried['detail']}")
        current = self._values().get("web")
        section: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
        for key in OLDER_KEYS:
            section.pop(key, None)
        section["enabled"] = True
        section["auth"] = body.auth.model_dump(exclude_defaults=True)
        if body.public_url and body.public_url.strip():
            section["public_url"] = body.public_url.strip().rstrip("/")
        else:
            section.pop("public_url", None)
        text = self._editor.replace_section(self._config.read(), "web", section)
        try:
            AppConfig.model_validate(yaml.safe_load(text) or {})
        except (yaml.YAMLError, ValidationError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        await self._config.write(text, f"aios.yaml: console login {body.auth.mode}")
        return web.json_response({"ok": True, "detail": tried["detail"]})

    @staticmethod
    async def _try(request: web.Request, auth: WebAuthConfig, you: str) -> dict[str, Any]:
        """Whether `auth` recognises the sender of `request` as `you`."""
        try:
            identity = WebIdentityFactory.from_auth(auth)
            email = await identity.email_of(request)
        except Exception as exc:  # noqa: BLE001 - a bad setting, reported rather than raised
            return {"ok": False, "email": None, "detail": str(exc)}
        if email is None:
            return {
                "ok": False,
                "email": None,
                "detail": "this browser's request would not be recognised: no valid token or "
                "header for these settings (check the domain, audience, header name)",
            }
        if email.casefold() != you.casefold():
            return {
                "ok": False,
                "email": email,
                "detail": f"this browser would be {email}, not you ({you})",
            }
        return {"ok": True, "email": email, "detail": f"you would be signed in as {email}"}

    @staticmethod
    def _effective(current: WebConfig) -> WebAuthConfig | None:
        """`auth`, or what the older keys mean, as one form."""
        if current.auth is not None:
            return current.auth
        if current.access_team_domain and current.access_aud:
            return WebAuthConfig(
                mode="cloudflare",
                team_domain=current.access_team_domain,
                audience=current.access_aud,
            )
        if current.dev_email:
            return WebAuthConfig(mode="dev", dev_email=current.dev_email)
        return None

    def _web(self) -> WebConfig:
        try:
            return AppConfig.model_validate(self._values()).web
        except ValidationError:
            return WebConfig()

    def _values(self) -> dict[str, Any]:
        try:
            loaded = yaml.safe_load(self._config.read()) or {}
        except yaml.YAMLError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
