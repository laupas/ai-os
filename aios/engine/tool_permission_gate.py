from typing import Any

from claude_agent_sdk import (
    CanUseTool,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from aios.agents.agent_tracker import AgentTracker
from aios.approvals.approval_policy import ApprovalPolicy
from aios.approvals.approval_service import ApprovalService
from aios.approvals.policy_verdict import PolicyVerdict
from aios.approvals.tool_call import ToolCall
from aios.tools.tool_context import ToolContext

YES, NO = "Yes", "No"


class ToolPermissionGate:
    """The SDK's `can_use_tool` hook: every tool call is decided here, in code.

    No tool is pre-allowed in the SDK options, so nothing bypasses this. The tracker
    names the agent making the call, so the policy can hold it to its grants.
    """

    def __init__(self, policy: ApprovalPolicy, approvals: ApprovalService) -> None:
        self._policy = policy
        self._approvals = approvals

    def for_context(self, context: ToolContext, tracker: AgentTracker) -> CanUseTool:
        async def check(
            tool_name: str, tool_input: dict[str, Any], permission: ToolPermissionContext
        ) -> PermissionResultAllow | PermissionResultDeny:
            decision = self._policy.evaluate(
                ToolCall(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    user=context.user,
                    conversation_id=context.conversation_id,
                    agent=tracker.name_of(permission.agent_id),
                )
            )
            if decision.verdict is PolicyVerdict.ALLOW:
                return PermissionResultAllow(updated_input=tool_input)
            if decision.verdict is PolicyVerdict.DENY:
                return PermissionResultDeny(message=decision.reason)
            answer = await self._approvals.request(
                context.conversation_id,
                context.binding,
                decision.question,
                [YES, NO],
                decision.approver_permission,
            )
            if answer == YES:
                return PermissionResultAllow(updated_input=tool_input)
            reason = (
                "The user declined." if answer else "Nobody approved in time, so it was not done."
            )
            return PermissionResultDeny(message=reason)

        return check
