import asyncio
import logging
import time
from typing import Any

import aiohttp
import jwt

from aios.web.login.login_refused import LoginRefused
from aios.web.login.sso.oidc_metadata import OidcMetadata

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)
CACHE_SECONDS = 3600


class OidcClient:
    """The HTTP half of an OpenID Connect sign-in: the provider's discovery
    document, the token request, and checking the ID token it answers with
    (signature against the provider's keys, issuer, audience, nonce, expiry)."""

    def __init__(self) -> None:
        self._metadata: dict[str, tuple[float, OidcMetadata]] = {}
        self._keys: dict[str, jwt.PyJWKClient] = {}

    async def discover(self, issuer: str) -> OidcMetadata:
        cached = self._metadata.get(issuer)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                async with session.get(url, headers={"Accept": "application/json"}) as response:
                    if response.status != 200:
                        raise LoginRefused(f"{url} answered {response.status}")
                    data = await response.json(content_type=None)
            meta = OidcMetadata.model_validate(data)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise LoginRefused(f"the provider's settings could not be read from {url}") from exc
        self._metadata[issuer] = (time.monotonic() + CACHE_SECONDS, meta)
        return meta

    async def exchange(
        self,
        meta: OidcMetadata,
        code: str,
        redirect_uri: str,
        verifier: str,
        client_id: str,
        client_secret: str | None,
    ) -> str:
        """The ID token for `code`."""
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "client_id": client_id,
        }
        if client_secret:
            form["client_secret"] = client_secret
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                async with session.post(
                    meta.token_endpoint, data=form, headers={"Accept": "application/json"}
                ) as response:
                    text = await response.text()
                    if response.status >= 400:
                        log.warning("sso: token request %s: %s", response.status, text[:300])
                        raise LoginRefused(f"the provider refused the sign-in: {text[:200]}")
                    data: dict[str, Any] = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise LoginRefused("the provider could not be reached") from exc
        token = data.get("id_token")
        if not isinstance(token, str):
            raise LoginRefused("the provider answered without an ID token")
        return token

    async def verify(
        self, meta: OidcMetadata, token: str, client_id: str, nonce: str
    ) -> dict[str, Any]:
        keys = self._keys.setdefault(meta.jwks_uri, jwt.PyJWKClient(meta.jwks_uri, lifespan=3600))
        try:
            key = await asyncio.to_thread(keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256", "PS256"],
                audience=client_id,
                issuer=meta.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            log.warning("sso: refused an ID token: %s", exc)
            raise LoginRefused("the provider's answer did not check out") from exc
        if claims.get("nonce") != nonce:
            raise LoginRefused("the provider's answer belongs to another sign-in")
        return claims
