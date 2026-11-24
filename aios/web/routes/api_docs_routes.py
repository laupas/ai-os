from collections.abc import Callable
from importlib.metadata import version

from aiohttp import web

from aios.config.app_config import AppConfig
from aios.entities.users.permission import Permission
from aios.web.api_docs.openapi_builder import OpenApiBuilder
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

SWAGGER = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14"
PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ai-os API</title>
<link rel="stylesheet" href="{SWAGGER}/swagger-ui.css">
</head>
<body>
<div id="docs"></div>
<script src="{SWAGGER}/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({{
  url: "/api/openapi.json",
  dom_id: "#docs",
  deepLinking: true,
  // Changes need the X-Aios header; the sign-in is this browser's own.
  requestInterceptor: (r) => {{
    r.headers["X-Aios"] = "1";
    r.credentials = "same-origin";
    return r;
  }},
}});
</script>
</body>
</html>"""


class ApiDocsRoutes(WebRoutes):
    """The console's API as OpenAPI, and a Swagger page to read and try it. Only
    while `api_docs.enabled` is on (checked on every request, so the switch applies
    at once), and only for administrators: otherwise 404."""

    def __init__(self, live: Callable[[], AppConfig], builder: OpenApiBuilder) -> None:
        self._live = live
        self._builder = builder

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/openapi.json", self._spec)
        app.router.add_get("/api/docs", self._page)

    async def _spec(self, request: web.Request) -> web.Response:
        """The OpenAPI description of this API."""
        self._check(request)
        return web.json_response(self._builder.build(request.app, version("aios")))

    async def _page(self, request: web.Request) -> web.Response:
        """This page."""
        self._check(request)
        return web.Response(text=PAGE, content_type="text/html")

    def _check(self, request: web.Request) -> None:
        if not self._live().api_docs.enabled:
            raise web.HTTPNotFound(text="the API docs are off: Settings → General")
        WebAuth.caller(request, Permission.ADMINISTER)
