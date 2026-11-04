from aios.crypto.fear_greed import FearGreed
from aios.crypto.http_json import HttpJson


class FearGreedClient:
    """The crypto Fear & Greed index from alternative.me."""

    def __init__(self, http: HttpJson) -> None:
        self._http = http

    async def current(self) -> FearGreed:
        data = await self._http.get("https://api.alternative.me/fng/", {"limit": "1"})
        entry = data["data"][0]
        return FearGreed(value=int(entry["value"]), classification=entry["value_classification"])
