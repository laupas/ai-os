from datetime import UTC, datetime, timedelta

from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.common.clock import Clock
from aios.crypto.rsi_calculator import RsiCalculator
from aios.crypto.signal_call import SignalCall
from aios.crypto.signal_rule import SignalRule
from aios.crypto.trade_limit_guard import TradeLimitGuard
from aios.crypto.trade_limits import TradeLimits
from aios.entities.trades.trade import Trade
from aios.entities.trades.trade_side import TradeSide
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.tools.crypto_trade_approval_rule import CryptoTradeApprovalRule

NOW = datetime(2026, 10, 9, 21, 30, tzinfo=UTC)  # 23:30 in Zurich


class _Clock(Clock):
    def now(self) -> datetime:
        return NOW


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
    collection: Collection[Trade] = Collection(
        CollectionDefinition(name="trades", entity=Trade), InMemoryDocumentStore()
    )
    for trade in trades:
        await collection.put(trade)
    return TradeLimitGuard(TradeLimits(), collection, _Clock(), "Europe/Zurich")


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


async def test_trade_rule_asks_or_refuses() -> None:
    rule = CryptoTradeApprovalRule(await _guard())
    user = User(id="u", name="U")

    def call(chf: object) -> ToolCall:
        return ToolCall(
            tool_name=CryptoTradeApprovalRule.TOOL,
            tool_input={"side": "buy", "coin": "btc", "chf": chf},
            user=user,
            conversation_id="c",
        )

    assert rule.evaluate(call(50)).verdict is PolicyVerdict.ASK  # type: ignore[union-attr]
    assert rule.evaluate(call(1000)).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]
    assert rule.evaluate(call("lots")).verdict is PolicyVerdict.DENY  # type: ignore[union-attr]
