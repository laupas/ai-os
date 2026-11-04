import asyncio
import logging

import jwt
from aiohttp import web

from aios.web.web_identity import WebIdentity

log = logging.getLogger(__name__)


class JwtHeaderIdentity(WebIdentity):
    """Reads the email from a signed token a login proxy puts on every request it
    let through, after checking its signature against the issuer's published keys,
    its audience and its issuer. A request that did not pass the proxy (another
    container on the network, say) has no valid token and gets None. Cloudflare
    Access is one such proxy; see `cloudflare`."""

    def __init__(
        self,
        header: str,
        jwks_url: str,
        issuer: str,
        audience: str,
        email_claim: str = "email",
        algorithms: list[str] | None = None,
    ) -> None:
        self._header = header
        self._issuer = issuer
        self._audience = audience
        self._email_claim = email_claim
        self._algorithms = algorithms or ["RS256", "ES256"]
        self._keys = jwt.PyJWKClient(jwks_url, lifespan=3600)

    @classmethod
    def cloudflare(cls, team_domain: str, audience: str) -> "JwtHeaderIdentity":
        issuer = f"https://{team_domain}"
        return cls(
            header="Cf-Access-Jwt-Assertion",
            jwks_url=f"{issuer}/cdn-cgi/access/certs",
            issuer=issuer,
            audience=audience,
            algorithms=["RS256"],
        )

    async def email_of(self, request: web.Request) -> str | None:
        token = request.headers.get(self._header)
        if not token:
            return None
        try:
            key = await asyncio.to_thread(self._keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            log.warning("refused a login token: %s", exc)
            return None
        email = claims.get(self._email_claim)
        return str(email) if email else None
