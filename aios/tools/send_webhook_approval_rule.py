import json

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.entities.webhooks.webhook_approval import WebhookApproval
from aios.entities.webhooks.webhook_destination import WebhookDestination
from aios.messaging.webhook.webhook_poster import WebhookPoster
from aios.storage.collection import Collection
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.send_webhook_tool import SendWebhookTool


class SendWebhookApprovalRule(ApprovalRule):
    """Each destination says whether a post is asked for, allowed or refused.
    Unknown destinations and fields that do not fit are refused before anyone is
    asked, so a human only ever approves a post that can go out."""

    TOOL = AiosToolServer.TOOL_PREFIX + SendWebhookTool.NAME

    def __init__(self, destinations: Collection[WebhookDestination]) -> None:
        self._destinations = destinations

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        if call.tool_name != self.TOOL:
            return None
        name = str(call.tool_input.get("destination", ""))
        destination = self._destinations.get(name)
        if destination is None or not destination.enabled:
            return PolicyDecision.deny(f"No webhook destination called {name!r}.")
        if destination.approval is WebhookApproval.DENY:
            return PolicyDecision.deny(f"Agents may not post to {name}.")
        fields = call.tool_input.get("fields") or {}
        if not isinstance(fields, dict):
            return PolicyDecision.deny("`fields` must be an object.")
        problems = WebhookPoster.problems(destination, fields)
        if problems:
            return PolicyDecision.deny(f"Fields do not fit {name}: {'; '.join(problems)}")
        if destination.approval is WebhookApproval.ALLOW:
            return PolicyDecision.allow()
        about = f" ({destination.description})" if destination.description else ""
        return PolicyDecision.ask(
            f"Post to webhook {name}{about}?\n\n{json.dumps(fields, ensure_ascii=False, indent=2)}"
        )
