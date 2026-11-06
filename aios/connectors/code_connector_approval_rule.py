import json
import logging

from aios.approvals.approval_rule import ApprovalRule
from aios.approvals.policy_decision import PolicyDecision
from aios.approvals.tool_call import ToolCall
from aios.connectors.code_connectors import CodeConnectors
from aios.connectors.connector_catalog import ConnectorCatalog

log = logging.getLogger(__name__)


class CodeConnectorApprovalRule(ApprovalRule):
    """Asks before the tools a code connector's manifest lists under
    `approval.always`, after asking the connector itself where it says `preflight`.

    A preflight that fails still asks, with the failure in the question: refusing
    would lock the tool, and saying nothing would hide that its own check broke.
    """

    def __init__(self, catalog: ConnectorCatalog, code: CodeConnectors) -> None:
        self._catalog = catalog
        self._code = code

    def evaluate(self, call: ToolCall) -> PolicyDecision | None:
        parts = call.tool_name.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            return None
        name, tool = parts[1], parts[2]
        connector = self._catalog.get(name)
        manifest = self._code.manifest_of(connector) if connector else None
        if manifest is None or tool not in manifest.approval.always:
            return None
        details = json.dumps(call.tool_input, ensure_ascii=False)[:500]
        question = f"Allow {name} {tool}?\n{details}"
        if tool in manifest.approval.preflight:
            config = self._catalog.server_config(name)
            try:
                answer = self._code.preflight(config or {}, tool, call.tool_input)
            except Exception as exc:  # noqa: BLE001 - any failure is reported, then asked
                log.warning("preflight of %s %s failed: %s", name, tool, exc)
                return PolicyDecision.ask(f"{question}\n(its own check failed: {exc})")
            if "deny" in answer:
                return PolicyDecision.deny(str(answer["deny"]))
            question = str(answer["ask"])
        return PolicyDecision.ask(question)
