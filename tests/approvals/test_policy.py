from aios.approvals.always_ask_rule import AlwaysAskRule
from aios.approvals.known_tools_rule import KnownToolsRule
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.rule_based_approval_policy import RuleBasedApprovalPolicy
from aios.approvals.tool_call import ToolCall
from aios.entities.users.user import User

USER = User(id="u", name="U")


def _call(tool: str) -> ToolCall:
    return ToolCall(tool_name=tool, tool_input={}, user=USER, conversation_id="c")


POLICY = RuleBasedApprovalPolicy(
    [
        KnownToolsRule(["WebSearch", "WebFetch"], lambda: ["mcp__aios__"]),
        AlwaysAskRule(["WebFetch"]),
    ]
)


def test_unknown_tools_are_denied() -> None:
    assert POLICY.evaluate(_call("Bash")).verdict is PolicyVerdict.DENY
    assert POLICY.evaluate(_call("mcp__other__x")).verdict is PolicyVerdict.DENY


def test_known_tools_are_allowed() -> None:
    assert POLICY.evaluate(_call("WebSearch")).verdict is PolicyVerdict.ALLOW
    assert POLICY.evaluate(_call("mcp__aios__data_query")).verdict is PolicyVerdict.ALLOW


def test_configured_tools_are_asked() -> None:
    decision = POLICY.evaluate(_call("WebFetch"))
    assert decision.verdict is PolicyVerdict.ASK and "WebFetch" in decision.question
