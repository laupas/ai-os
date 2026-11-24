import base64
import hashlib
import json
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import jwt
from aiohttp import web
from aiohttp.test_utils import TestServer
from cryptography.hazmat.primitives.asymmetric import rsa

CLIENT_ID = "ai-os-test"
CLIENT_SECRET = "s3cret"


class FakeOidcProvider:
    """An OpenID provider on localhost: discovery, keys, and a token endpoint that
    signs whatever `claims` say for the next sign-in. `authorize` reads the
    address ai-os sent the browser to, as the provider's login page would."""

    def __init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims: dict[str, Any] = {}
        self.codes: dict[str, dict[str, str]] = {}
        self.server: TestServer | None = None

    @property
    def issuer(self) -> str:
        assert self.server is not None
        return str(self.server.make_url("")).rstrip("/")

    async def __aenter__(self) -> "FakeOidcProvider":
        app = web.Application()
        app.router.add_get("/.well-known/openid-configuration", self._discovery)
        app.router.add_get("/keys", self._keys)
        app.router.add_post("/token", self._token)
        self.server = TestServer(app, host="127.0.0.1")
        await self.server.start_server()
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self.server is not None
        await self.server.close()

    def authorize(self, location: str, code: str = "the-code") -> dict[str, str]:
        """Takes the authorization request; returns its query."""
        query = {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
        self.codes[code] = query
        return query

    def id_token(self, nonce: str, **override: Any) -> str:
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": CLIENT_ID,
            "sub": "user-1",
            "iat": now,
            "exp": now + 300,
            "nonce": nonce,
            **self.claims,
            **override,
        }
        return jwt.encode(claims, self._key, algorithm="RS256", headers={"kid": "k1"})

    async def _discovery(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "issuer": self.issuer,
                "authorization_endpoint": f"{self.issuer}/authorize",
                "token_endpoint": f"{self.issuer}/token",
                "jwks_uri": f"{self.issuer}/keys",
            }
        )

    async def _keys(self, request: web.Request) -> web.Response:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self._key.public_key()))
        return web.json_response({"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]})

    async def _token(self, request: web.Request) -> web.Response:
        form = await request.post()
        asked = self.codes.pop(str(form.get("code")), None)
        if asked is None or form.get("client_secret") != CLIENT_SECRET:
            return web.json_response({"error": "invalid_grant"}, status=400)
        verifier = str(form.get("code_verifier"))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        if challenge.decode().rstrip("=") != asked["code_challenge"]:
            return web.json_response({"error": "invalid_grant"}, status=400)
        if form.get("redirect_uri") != asked["redirect_uri"]:
            return web.json_response({"error": "invalid_grant"}, status=400)
        return web.json_response({"access_token": "a", "id_token": self.id_token(asked["nonce"])})
