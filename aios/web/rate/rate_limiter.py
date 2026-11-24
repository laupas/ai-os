import logging
import math
import time
from collections.abc import Callable

from aiohttp import web

from aios.config.rate_limit_config import RateLimitConfig
from aios.users.group_limits import GroupLimits
from aios.web.client_address import ClientAddress
from aios.web.rate.rate_buckets import RateBuckets
from aios.web.web_auth import CALLER

log = logging.getLogger(__name__)

LOGIN_PATHS = ("/api/login", "/api/oauth/callback")
HOOKS = "/hooks/"
# Requests that start work costing tokens or transcription: counted on their own.
MESSAGES = frozenset(
    {
        ("POST", "/api/conversations"),
        ("POST", "/api/conversations/{id}/messages"),
        ("POST", "/api/voice/transcriptions"),
        ("POST", "/api/triggers/{id}/run"),
    }
)


class RateLimiter:
    """Answers 429 (with `Retry-After`) to whoever asks too often. Two middlewares:
    `before_auth` counts per client address what anyone can reach without signing
    in (the login routes, webhooks), and blocks an address that keeps sending wrong
    webhook tokens; `after_auth` counts per user: messages, reads and writes on
    their own, messages by the user's groups where they set a limit. The limits
    come from aios.yaml as it is now."""

    def __init__(
        self,
        config: Callable[[], RateLimitConfig],
        address: ClientAddress,
        groups: GroupLimits | None = None,
        buckets: RateBuckets | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._address = address
        self._groups = groups
        self._buckets = buckets or RateBuckets(now)
        self._now = now
        self._hook_failures: dict[str, list[float]] = {}

    @web.middleware
    async def before_auth(self, request: web.Request, handler):  # type: ignore[no-untyped-def]
        config = self._config()
        if not config.enabled:
            return await handler(request)
        path = request.path
        if path.startswith(LOGIN_PATHS):
            client = self._address.of(request)
            self._take(f"login:{client}", config.login_per_minute, client)
            return await handler(request)
        if path.startswith(HOOKS):
            client = self._address.of(request)
            if self._blocked(client, config):
                raise self._too_many(config.hook_block_minutes * 60)
            self._take(f"hooks:{client}", config.hooks_per_minute, client)
            try:
                response = await handler(request)
            except web.HTTPNotFound:
                self._failed(client)
                raise
            if response.status == 404:
                self._failed(client)
            return response
        return await handler(request)

    @web.middleware
    async def after_auth(self, request: web.Request, handler):  # type: ignore[no-untyped-def]
        config = self._config()
        caller = request.get(CALLER)
        if not config.enabled or caller is None:
            return await handler(request)
        route = request.match_info.route.resource
        canonical = route.canonical if route is not None else request.path
        if (request.method, canonical) in MESSAGES:
            own = self._groups.messages_per_minute(caller.user) if self._groups else None
            kind, limit = "messages", own or config.messages_per_minute
        elif request.method in ("GET", "HEAD"):
            kind, limit = "reads", config.reads_per_minute
        else:
            kind, limit = "writes", config.writes_per_minute
        self._take(f"{kind}:{caller.user.id}", limit, caller.user.name)
        return await handler(request)

    def _take(self, key: str, per_minute: int, who: str) -> None:
        wait = self._buckets.take(key, per_minute)
        if wait > 0:
            log.warning("web: too many requests (%s) from %s", key.split(":")[0], who)
            raise self._too_many(wait)

    def _blocked(self, client: str, config: RateLimitConfig) -> bool:
        since = self._now() - config.hook_block_minutes * 60
        recent = [t for t in self._hook_failures.get(client, []) if t > since]
        if recent:
            self._hook_failures[client] = recent
        else:
            self._hook_failures.pop(client, None)
        return len(recent) >= config.hook_failures

    def _failed(self, client: str) -> None:
        self._hook_failures.setdefault(client, []).append(self._now())

    @staticmethod
    def _too_many(seconds: float) -> web.HTTPTooManyRequests:
        return web.HTTPTooManyRequests(
            text="too many requests; try again shortly",
            headers={"Retry-After": str(max(1, math.ceil(seconds)))},
        )
