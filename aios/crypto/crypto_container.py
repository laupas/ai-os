from dependency_injector import containers, providers

from aios.crypto.coin_gecko_client import CoinGeckoClient
from aios.crypto.crypto_signal_service import CryptoSignalService
from aios.crypto.fear_greed_client import FearGreedClient
from aios.crypto.http_json import HttpJson
from aios.crypto.kraken_client import KrakenClient
from aios.crypto.kraken_trader import KrakenTrader
from aios.crypto.rsi_calculator import RsiCalculator
from aios.crypto.signal_rule import SignalRule
from aios.crypto.trade_limit_guard import TradeLimitGuard


class CryptoContainer(containers.DeclarativeContainer):
    settings = providers.Dependency()
    limits = providers.Dependency()
    trades = providers.Dependency()
    clock = providers.Dependency()
    ids = providers.Dependency()
    timezone = providers.Dependency()

    http = providers.Singleton(HttpJson)
    signals = providers.Singleton(
        CryptoSignalService,
        gecko=providers.Singleton(CoinGeckoClient, http=http),
        fear_greed=providers.Singleton(FearGreedClient, http=http),
        rsi=providers.Singleton(RsiCalculator),
        rule=providers.Singleton(SignalRule),
    )
    guard = providers.Singleton(
        TradeLimitGuard, limits=limits, trades=trades, clock=clock, timezone=timezone
    )
    trader = providers.Singleton(
        KrakenTrader,
        client=providers.Singleton(
            KrakenClient,
            http=http,
            api_key=settings.provided.kraken_api_key,
            api_secret=settings.provided.kraken_api_secret,
        ),
        guard=guard,
        limits=limits,
        trades=trades,
        clock=clock,
        ids=ids,
    )
