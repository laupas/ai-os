import base64
import json
import logging
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp

from aios.connectors.oauth_error import OAuthError
from aios.connectors.oauth_metadata import OAuthMetadata

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)
PREFERRED_AUTH = ("client_secret_basic", "client_secret_post", "none")


class OAuthClient:
    """The HTTP half of MCP authorization: discovery (RFC 9728, RFC 8414), dynamic
    client registration (RFC 7591) and the token endpoint (authorization code with
    PKCE, refresh)."""

    async def discover(self, server_url: str) -> OAuthMetadata:
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(server_url))
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            resource_meta = await self._get_json(
                session, urljoin(origin, "/.well-known/oauth-protected-resource")
            )
            resource = (resource_meta or {}).get("resource") or server_url
            servers = (resource_meta or {}).get("authorization_servers") or [origin]
            issuer = servers[0].rstrip("/")
            meta = await self._get_json(session, f"{issuer}/.well-known/oauth-authorization-server")
            if meta is None:
                meta = await self._get_json(session, f"{issuer}/.well-known/openid-configuration")
        if not meta or "authorization_endpoint" not in meta or "token_endpoint" not in meta:
            raise OAuthError(f"{origin} does not offer an OAuth sign-in")
        return OAuthMetadata(
            resource=resource,
            authorization_endpoint=meta["authorization_endpoint"],
            token_endpoint=meta["token_endpoint"],
            registration_endpoint=meta.get("registration_endpoint"),
            auth_methods=meta.get("token_endpoint_auth_methods_supported")
            or ["client_secret_basic"],
            scopes=(resource_meta or {}).get("scopes_supported")
            or meta.get("scopes_supported")
            or [],
        )

    async def register(self, meta: OAuthMetadata, redirect_uri: str) -> tuple[str, str | None, str]:
        """Registers ai-os as a client; returns its id, its secret and how it
        authenticates at the token endpoint."""
        if not meta.registration_endpoint:
            raise OAuthError("the server does not let clients register themselves")
        method = next((m for m in PREFERRED_AUTH if m in meta.auth_methods), "none")
        body = {
            "client_name": "ai-os",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": method,
        }
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(meta.registration_endpoint, json=body) as response:
                data = await self._json(response, "registering ai-os")
        return (
            data["client_id"],
            data.get("client_secret"),
            data.get("token_endpoint_auth_method", method),
        )

    async def token(
        self,
        token_endpoint: str,
        fields: dict[str, str],
        client_id: str,
        client_secret: str | None,
        auth_method: str,
    ) -> dict[str, Any]:
        """One token request (an authorization code or a refresh token)."""
        headers = {"Accept": "application/json"}
        form = dict(fields)
        if auth_method == "client_secret_basic" and client_secret:
            pair = f"{client_id}:{client_secret}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(pair).decode()
        else:
            form["client_id"] = client_id
            if auth_method == "client_secret_post" and client_secret:
                form["client_secret"] = client_secret
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(token_endpoint, data=form, headers=headers) as response:
                data = await self._json(response, "getting a token")
        if "access_token" not in data:
            raise OAuthError("the server answered without an access token")
        return data

    @staticmethod
    async def _get_json(session: aiohttp.ClientSession, url: str) -> dict[str, Any] | None:
        try:
            async with session.get(url, headers={"Accept": "application/json"}) as response:
                if response.status != 200:
                    return None
                return await response.json(content_type=None)
        except (aiohttp.ClientError, ValueError):
            return None

    @staticmethod
    async def _json(response: aiohttp.ClientResponse, doing: str) -> dict[str, Any]:
        text = await response.text()
        if response.status >= 400:
            log.warning("%s failed: %s %s", doing, response.status, text[:300])
            raise OAuthError(f"{doing} failed ({response.status}): {text[:200]}")
        try:
            return json.loads(text)
        except ValueError as exc:
            raise OAuthError(f"{doing}: the answer is not JSON") from exc
