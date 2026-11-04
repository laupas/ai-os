from aios.crypto.coin_market import CoinMarket
from aios.crypto.http_json import HttpJson

API = "https://api.coingecko.com/api/v3"
ALIASES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "xrp": "ripple",
    "doge": "dogecoin",
    "dot": "polkadot",
    "avax": "avalanche-2",
    "link": "chainlink",
    "matic": "matic-network",
}


class CoinGeckoClient:
    """Public CoinGecko endpoints, no key needed."""

    def __init__(self, http: HttpJson) -> None:
        self._http = http

    async def resolve_ids(self, names: list[str]) -> list[str]:
        ids, unknown = [], []
        for name in names:
            key = name.strip().lower()
            if key in ALIASES.values():
                ids.append(key)
            elif key in ALIASES:
                ids.append(ALIASES[key])
            else:
                unknown.append(key)
        if unknown:
            coins = await self._http.get(f"{API}/coins/list")
            by_symbol = {c["symbol"].lower(): c["id"] for c in coins}
            by_id = {c["id"] for c in coins}
            ids += [
                u if u in by_id else by_symbol[u] for u in unknown if u in by_id or u in by_symbol
            ]
        return list(dict.fromkeys(ids))

    async def markets(self, ids: list[str]) -> list[CoinMarket]:
        rows = await self._http.get(
            f"{API}/coins/markets",
            {
                "vs_currency": "usd",
                "ids": ",".join(ids),
                "price_change_percentage": "24h,7d,30d",
            },
        )
        return [
            CoinMarket(
                id=r["id"],
                symbol=r["symbol"].upper(),
                price_usd=r["current_price"],
                change_24h=r.get("price_change_percentage_24h"),
                change_7d=r.get("price_change_percentage_7d_in_currency"),
                change_30d=r.get("price_change_percentage_30d_in_currency"),
            )
            for r in rows
        ]

    async def daily_closes(self, coin_id: str, days: int = 30) -> list[float]:
        data = await self._http.get(
            f"{API}/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": str(days), "interval": "daily"},
        )
        return [float(point[1]) for point in data["prices"]]
