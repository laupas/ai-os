from aiohttp import web


class PublicAddress:
    """The address browsers reach the console at, for a provider to send them back
    to: `web.public_url`, else the request's host."""

    def __init__(self, public_url: str | None) -> None:
        self._public_url = public_url

    def of(self, request: web.Request, path: str) -> str:
        if self._public_url:
            return self._public_url.rstrip("/") + path
        # Behind the tunnel the hop to ai-os is plain http, so the scheme the
        # browser used is not on the request; a public host is always https.
        host = request.host
        local = host.split(":")[0] in {"localhost", "127.0.0.1"}
        return f"{'http' if local else 'https'}://{host}{path}"

    def secure(self, request: web.Request) -> bool:
        """Whether browsers reach the console over https, so its cookies can be
        marked Secure: `public_url` says so, or the request (or the proxy in front)
        does. Unknown, they are not, or a console on plain http could not sign in."""
        if self._public_url:
            return self._public_url.startswith("https://")
        return request.secure or request.headers.get("X-Forwarded-Proto") == "https"
