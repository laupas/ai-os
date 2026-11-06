import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

from http_json import HttpJson
from kraken_error import KrakenError

API = "https://api.kraken.com"


class KrakenClient:
    """Kraken REST: public calls, and private calls signed as Kraken documents."""

    def __init__(self, http: HttpJson, api_key: str | None, api_secret: str | None) -> None:
        self._http = http
        self._api_key = (api_key or "").strip()
        self._api_secret = (api_secret or "").strip()

    def has_credentials(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def public(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        return self._result(await self._http.post_form(f"{API}{endpoint}", params))

    async def private(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        if not self.has_credentials():
            raise KrakenError("KRAKEN_API_KEY and KRAKEN_API_SECRET are not set")
        nonce = str(int(time.time() * 1000))
        form = {"nonce": nonce, **params}
        headers = {"API-Key": self._api_key, "API-Sign": self._sign(endpoint, form, nonce)}
        return self._result(await self._http.post_form(f"{API}{endpoint}", form, headers))

    def _sign(self, endpoint: str, form: dict[str, str], nonce: str) -> str:
        body = urllib.parse.urlencode(form)
        digest = hashlib.sha256((nonce + body).encode()).digest()
        mac = hmac.new(
            base64.b64decode(self._api_secret), endpoint.encode() + digest, hashlib.sha512
        )
        return base64.b64encode(mac.digest()).decode()

    @staticmethod
    def _result(response: dict[str, Any]) -> dict[str, Any]:
        if response.get("error"):
            raise KrakenError("; ".join(response["error"]))
        return response.get("result") or {}
