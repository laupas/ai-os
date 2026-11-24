import logging
from pathlib import Path

from aiohttp import web

from aios.bootstrap.background_service import BackgroundService
from aios.web.audit_middleware import AuditMiddleware
from aios.web.restart_request import RestartRequest
from aios.web.security_headers import SecurityHeaders
from aios.web.web_auth import WebAuth
from aios.web.web_routes import WebRoutes

log = logging.getLogger(__name__)

# The built console (web/, `npm run build`), copied here by the Dockerfile.
STATIC_DIR = Path(__file__).parent / "static"
IMMUTABLE = "public, max-age=31536000, immutable"
# aiohttp refuses a header over 8 KiB. A browser sends every cookie of the host, and
# other apps on the same host (localhost, above all) can push the Cookie header
# past that; the console would then answer nothing but a 400.
HEADER_LIMITS = {"max_line_size": 64 * 1024, "max_field_size": 64 * 1024}
NOT_BUILT = (
    "<!doctype html><title>ai-os</title><p>The web console is not built. "
    "Run <code>npm run build</code> in <code>web/</code>, or use the Docker image.</p>"
)


class WebServer(BackgroundService):
    """Serves the console: the built page from `static_dir` and the JSON API from the
    routes. Runs until a restart is requested, which ends the application.

    The page is never cached and names its scripts by content hash, which are cached
    for good. Cloudflare caches `.js` and `.css` at its edge by default, and a browser
    running a previous build against the current API shows a page that half works.
    """

    def __init__(
        self,
        auth: WebAuth,
        routes: list[WebRoutes],
        restart: RestartRequest,
        port: int,
        static_dir: Path = STATIC_DIR,
        audit: AuditMiddleware | None = None,
        security: SecurityHeaders | None = None,
    ) -> None:
        self._security = security or SecurityHeaders()
        self._auth = auth
        self._routes = routes
        self._restart = restart
        self._port = port
        self._static_dir = Path(static_dir)
        self._audit = audit

    def build(self) -> web.Application:
        # Audit inside auth: it records only what an identified caller did.
        middlewares = [self._auth.middleware]
        if self._audit is not None:
            middlewares.append(self._audit.middleware)
        app = web.Application(middlewares=middlewares, client_max_size=1024**2)
        app.on_response_prepare.append(self._caching)
        app.on_response_prepare.append(self._security.on_prepare)
        for routes in self._routes:
            routes.register(app)
        app.router.add_get("/", self._index)
        if self._static_dir.is_dir():
            app.router.add_static("/static", self._static_dir)
        return app

    async def run(self) -> None:
        runner = web.AppRunner(self.build(), access_log=None, **HEADER_LIMITS)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", self._port).start()
        log.info("web console listening on port %d", self._port)
        try:
            await self._restart.wait()
            log.info("restart requested from the web console")
        finally:
            await runner.cleanup()

    async def _index(self, request: web.Request) -> web.StreamResponse:
        index = self._static_dir / "index.html"
        if not index.is_file():
            return web.Response(text=NOT_BUILT, content_type="text/html")
        return web.FileResponse(index)

    @staticmethod
    async def _caching(request: web.Request, response: web.StreamResponse) -> None:
        hashed = request.path.startswith("/static/assets/") and response.status == 200
        response.headers.setdefault("Cache-Control", IMMUTABLE if hashed else "no-cache")
