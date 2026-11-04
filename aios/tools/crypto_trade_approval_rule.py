from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.crypto.trade_limit_guard import TradeLimitGuard
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.crypto_trade_tool import CryptoTradeTool


class CryptoTradeApprovalRule(ApprovalRule):
    """Every order is asked first. One the limits would refuse is not even asked."""

    TOOL = AiosToolServer.TOOL_PREFIX + CryptoTradeTool.NAME

    def __init__(self, guard: TradeLimitGuard) -> None:
        self._guard = guard

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name != self.TOOL:
            return None
        side = str(call.tool_input.get("side", ""))
        coin = str(call.tool_input.get("coin", "")).upper()
        try:
            chf = float(call.tool_input.get("chf", 0))
        except (TypeError, ValueError):
            return PolicyDecision.deny("The order needs a numeric CHF amount.")
        reason = self._guard.check_order(side, coin, chf)
        if reason:
            return PolicyDecision.deny(f"The trading limits refuse this order: {reason}.")
        return PolicyDecision.ask(
            f"Place a market order on Kraken: {side} {coin} for {chf:.2f} CHF?"
        )
