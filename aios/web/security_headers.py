from aiohttp import web

from aios.web.public_address import PublicAddress

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        # Radix and CodeMirror set styles inline.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "media-src 'self' blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeaders:
    """The headers every response gets, so a browser holds the console to what it
    does: its own scripts only (Content-Security-Policy), never inside another
    site's frame (clickjacking), no guessing of content types, no referrer to other
    sites, the microphone for voice only, and https only once it was reached over
    https (HSTS). A route that needs another policy (the API docs page) sets its own
    `Content-Security-Policy`, which is kept."""

    def __init__(self, public_url: str | None = None) -> None:
        self._address = PublicAddress(public_url)

    async def on_prepare(self, request: web.Request, response: web.StreamResponse) -> None:
        headers = response.headers
        headers.setdefault("Content-Security-Policy", CSP)
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", "same-origin")
        headers.setdefault(
            "Permissions-Policy", "camera=(), geolocation=(), microphone=(self), payment=()"
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if self._address.secure(request):
            headers.setdefault("Strict-Transport-Security", HSTS)
