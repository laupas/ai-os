import hmac
import ipaddress
import logging

from aiohttp import web

from aios.web.web_identity import WebIdentity

log = logging.getLogger(__name__)


class TrustedHeaderIdentity(WebIdentity):
    """Reads the email from a plain header a login proxy sets (Authelia, Traefik
    forward-auth, oauth2-proxy without tokens, …).

    A plain header proves nothing by itself: anything that reaches ai-os directly
    can send it. So it is believed only from a connection out of `trusted_proxies`,
    and/or when the request also carries `secret` in `secret_header`, which only
    the proxy knows. At least one of the two is required.
    """

    def __init__(
        self,
        header: str,
        trusted_proxies: list[str],
        secret_header: str,
        secret: str | None,
    ) -> None:
        if not trusted_proxies and not secret:
            raise ValueError("a trusted header needs trusted proxies or a secret")
        self._header = header
        self._networks = [ipaddress.ip_network(p, strict=False) for p in trusted_proxies]
        self._secret_header = secret_header
        self._secret = secret

    async def email_of(self, request: web.Request) -> str | None:
        if self._networks and not self._from_proxy(request.remote):
            return None
        if self._secret:
            sent = request.headers.get(self._secret_header, "")
            if not hmac.compare_digest(sent.encode(), self._secret.encode()):
                return None
        email = request.headers.get(self._header, "").strip()
        return email or None

    def _from_proxy(self, remote: str | None) -> bool:
        try:
            address = ipaddress.ip_address(remote or "")
        except ValueError:
            return False
        return any(address in network for network in self._networks)
