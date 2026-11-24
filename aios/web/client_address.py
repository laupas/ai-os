import ipaddress

from aiohttp import web

HEADERS = ("CF-Connecting-IP", "X-Real-IP")


class ClientAddress:
    """Where a request really comes from. Behind a proxy the connection is the
    proxy's, and the client is in a header the proxy sets; that header is believed
    only when the connection comes from `trusted_proxies`, or anyone could choose
    their own address by sending it."""

    def __init__(self, trusted_proxies: list[str]) -> None:
        self._networks = [ipaddress.ip_network(p, strict=False) for p in trusted_proxies]

    def of(self, request: web.Request) -> str:
        remote = request.remote or ""
        if not self._trusted(remote):
            return remote
        for header in HEADERS:
            value = request.headers.get(header, "").strip()
            if value:
                return value[:64]
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return (forwarded or remote)[:64]

    def _trusted(self, remote: str) -> bool:
        try:
            address = ipaddress.ip_address(remote)
        except ValueError:
            return False
        return any(address in network for network in self._networks)
