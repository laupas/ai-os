import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

CRYPTO = Path(__file__).parents[2] / "connectors" / "crypto"
sys.path.insert(0, str(CRYPTO))

from crypto_connector import CryptoConnector  # noqa: E402
from rsi_calculator import RsiCalculator  # noqa: E402
from signal_call import SignalCall  # noqa: E402
from signal_rule import SignalRule  # noqa: E402
from trade import Trade  # noqa: E402
from trade_limit_guard import TradeLimitGuard  # noqa: E402
from trade_limits import TradeLimits  # noqa: E402
from trade_log import TradeLog  # noqa: E402
from trade_side import TradeSide  # noqa: E402

NOW = datetime(2026, 10, 9, 21, 30, tzinfo=UTC)  # 23:30 in Zurich


def _trade(chf: float, at: datetime) -> Trade:
    return Trade(
        id=str(int(at.timestamp())),
        side=TradeSide.BUY,
        coin="BTC",
        pair="XBTCHF",
        chf_amount=chf,
        executed_volume=0.001,
        executed_price=60000,
        executed_cost_chf=chf,
        fee_chf=0.4,
        order_id="o",
        executed_at=at,
    )


async def _guard(*trades: Trade) -> TradeLimitGuard:
    log = TradeLog(Path(tempfile.mkdtemp(prefix="aios-trades-")))
    for trade in trades:
        log.add(trade)
    return TradeLimitGuard(TradeLimits(), log, lambda: NOW, "Europe/Zurich")


def test_rsi() -> None:
    rising = [float(i) for i in range(30)]
    assert RsiCalculator().rsi(rising) == 100.0
    assert RsiCalculator().rsi([1.0, 2.0]) is None
    zigzag = [100 + (i % 2) * 2 for i in range(30)]
    assert 40 < RsiCalculator().rsi(zigzag) < 60  # type: ignore[operator]


def test_signal_rule() -> None:
    rule = SignalRule()
    assert rule.decide(25, 20) is SignalCall.BUY
    assert rule.decide(75, 80) is SignalCall.SELL
    assert rule.decide(50, 30) is SignalCall.LEAN_BUY
    assert rule.decide(68, None) is SignalCall.LEAN_SELL
    assert rule.decide(50, 50) is SignalCall.HOLD
    assert rule.decide(None, None) is SignalCall.HOLD


async def test_order_limits() -> None:
    guard = await _guard()
    assert guard.check_order("buy", "BTC", 50) is None
    assert "not tradable" in guard.check_order("buy", "DOGE", 50)  # type: ignore[operator]
    assert "minimum" in guard.check_order("buy", "BTC", 5)  # type: ignore[operator]
    assert "per-order" in guard.check_order("buy", "BTC", 250)  # type: ignore[operator]
    assert "side" in guard.check_order("hold", "BTC", 50)  # type: ignore[operator]


async def test_daily_cap_counts_the_local_day() -> None:
    # 22:00 UTC yesterday is 00:00 today in Zurich: it counts. 21:00 UTC yesterday does not.
    today = NOW.replace(hour=0) - timedelta(hours=2)
    guard = await _guard(_trade(200, today), _trade(200, today + timedelta(minutes=5)))
    assert "daily 500" in guard.check_order("buy", "BTC", 150)  # type: ignore[operator]
    assert guard.check_order("buy", "BTC", 100) is None
    guard_yesterday = await _guard(_trade(200, NOW.replace(hour=0) - timedelta(hours=3)))
    assert guard_yesterday.trades_today() == []


async def test_cooldown_and_order_count() -> None:
    guard = await _guard(_trade(10, NOW - timedelta(seconds=20)))
    assert "cooldown" in guard.check_order("buy", "BTC", 10)  # type: ignore[operator]
    many = [_trade(10, NOW - timedelta(minutes=10 + i)) for i in range(5)]
    assert "5 orders" in (await _guard(*many)).check_order("buy", "BTC", 10)  # type: ignore[operator]


def test_preflight_asks_or_refuses(tmp_path) -> None:
    connector = CryptoConnector({"AIOS_CONNECTOR_STATE": str(tmp_path)})
    assert (
        "Place a market order"
        in connector.preflight("trade", {"side": "buy", "coin": "btc", "chf": 50})["ask"]
    )
    assert (
        "per-order"
        in connector.preflight("trade", {"side": "buy", "coin": "BTC", "chf": 1000})["deny"]
    )
    assert (
        "numeric"
        in connector.preflight("trade", {"side": "buy", "coin": "BTC", "chf": "lots"})["deny"]
    )


def test_settings_are_the_limits(tmp_path) -> None:
    env = {
        "AIOS_CONNECTOR_STATE": str(tmp_path),
        "AIOS_CONNECTOR_SETTINGS": '{"max_chf_per_order": 20}',
    }
    assert (
        "per-order cap of 20"
        in CryptoConnector(env).preflight("trade", {"side": "buy", "coin": "BTC", "chf": 50})[
            "deny"
        ]
    )


def test_an_unset_variable_is_no_key(tmp_path) -> None:
    env = {"AIOS_CONNECTOR_STATE": str(tmp_path), "KRAKEN_API_KEY": "${KRAKEN_API_KEY}"}
    assert not CryptoConnector(env).trader._client.has_credentials()


def test_the_manifest_describes_the_limits_the_code_applies() -> None:
    manifest = yaml.safe_load((CRYPTO / "connector.yaml").read_text())
    defaults = {k: p["default"] for k, p in manifest["settings"]["properties"].items()}
    assert defaults == TradeLimits().model_dump()
