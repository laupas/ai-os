import base64
import hashlib

from aiohttp import web
from aiohttp.test_utils import TestServer


class FakeOAuthServer:
    """An MCP server's OAuth side as Homey's looks: protected-resource and
    authorization-server metadata, dynamic registration, a token endpoint with
    client_secret_basic, PKCE and refresh. `authorize(challenge)` stands in for
    the person signing in and returns the code the browser would carry back."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}
        self.refreshes = 0
        app = web.Application()
        app.router.add_get("/.well-known/oauth-protected-resource", self._resource)
        app.router.add_get("/.well-known/oauth-authorization-server", self._metadata)
        app.router.add_post("/oauth2/client", self._register)
        app.router.add_post("/oauth2/token", self._token)
        self.server = TestServer(app)

    @property
    def url(self) -> str:
        return str(self.server.make_url("")).rstrip("/")

    def authorize(self, challenge: str) -> str:
        code = f"code-{len(self.codes)}"
        self.codes[code] = challenge
        return code

    async def _resource(self, _: web.Request) -> web.Response:
        return web.json_response({"resource": self.url, "authorization_servers": [self.url]})

    async def _metadata(self, _: web.Request) -> web.Response:
        return web.json_response(
            {
                "authorization_endpoint": f"{self.url}/oauth2/authorise",
                "token_endpoint": f"{self.url}/oauth2/token",
                "registration_endpoint": f"{self.url}/oauth2/client",
                "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            }
        )

    async def _register(self, request: web.Request) -> web.Response:
        body = await request.json()
        assert body["token_endpoint_auth_method"] == "client_secret_basic"
        return web.json_response({"client_id": "cid", "client_secret": "secret"}, status=201)

    async def _token(self, request: web.Request) -> web.Response:
        expected = "Basic " + base64.b64encode(b"cid:secret").decode()
        if request.headers.get("Authorization") != expected:
            return web.json_response({"error": "invalid_client"}, status=401)
        form = await request.post()
        if form["grant_type"] == "refresh_token":
            self.refreshes += 1
            return web.json_response(
                {"access_token": f"access-r{self.refreshes}", "expires_in": 3600}
            )
        challenge = self.codes.pop(str(form["code"]), None)
        digest = hashlib.sha256(str(form["code_verifier"]).encode()).digest()
        if challenge != base64.urlsafe_b64encode(digest).decode().rstrip("="):
            return web.json_response({"error": "invalid_grant"}, status=400)
        return web.json_response(
            {"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 60}
        )
