from typing import Any

import aiohttp


class HttpJson:
    """Small JSON-over-HTTP helper shared by the market clients."""

    def __init__(self, timeout_seconds: float = 10) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def get(self, url: str, params: dict[str, str] | None = None) -> Any:
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json(content_type=None)

    async def post_form(
        self, url: str, form: dict[str, str], headers: dict[str, str] | None = None
    ) -> Any:
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(url, data=form, headers=headers or {}) as response:
                return await response.json(content_type=None)
