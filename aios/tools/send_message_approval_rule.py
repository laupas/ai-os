from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.send_message_tool import SendMessageTool
from aios.users.authorizer import Authorizer


class SendMessageApprovalRule(ApprovalRule):
    """Users with `receive_unapproved` get messages directly; anyone else only
    after a human said yes. Unknown recipients are refused outright."""

    TOOL = AiosToolServer.TOOL_PREFIX + SendMessageTool.NAME

    def __init__(self, users: Collection[User], authorizer: Authorizer) -> None:
        self._users = users
        self._authorizer = authorizer

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name != self.TOOL:
            return None
        recipient = str(call.tool_input.get("recipient", ""))
        via = str(call.tool_input.get("via", ""))
        user = self._users.find(lambda u: u.matches_name(recipient))
        if user is None:
            return PolicyDecision.deny(f"No user called {recipient!r}.")
        account = user.account_for(via)
        if account is None:
            return PolicyDecision.deny(f"{user.name} has no {via} account.")
        if self._authorizer.has(user, Permission.RECEIVE_UNAPPROVED):
            return PolicyDecision.allow()
        return PolicyDecision.ask(
            f"Send this {via} message to {user.name} ({account.address})?\n\n"
            f"{call.tool_input.get('text', '')}"
        )
