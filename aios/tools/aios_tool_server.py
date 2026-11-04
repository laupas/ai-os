import logging
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server, tool

from aios.tools.aios_tool import AiosTool
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError

log = logging.getLogger(__name__)


class AiosToolServer:
    """Exposes the ai-os tools to the agent as one in-process MCP server."""

    SERVER_NAME = "aios"
    TOOL_PREFIX = f"mcp__{SERVER_NAME}__"

    def __init__(self, tools: list[AiosTool]) -> None:
        self._tools = tools

    def tool_names(self) -> list[str]:
        return [t.name for t in self._tools]

    def build(self, context: ToolContext) -> McpSdkServerConfig:
        return create_sdk_mcp_server(
            name=self.SERVER_NAME, tools=[self._wrap(t, context) for t in self._tools]
        )

    @staticmethod
    def _wrap(aios_tool: AiosTool, context: ToolContext) -> SdkMcpTool[Any]:
        async def handler(args: dict[str, Any]) -> dict[str, Any]:
            try:
                text = await aios_tool.run(args, context)
                return {"content": [{"type": "text", "text": text}]}
            except ToolError as exc:
                return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
            except Exception as exc:
                log.exception("tool %s failed", aios_tool.name)
                return {
                    "content": [{"type": "text", "text": f"Tool failed: {exc}"}],
                    "is_error": True,
                }

        return tool(aios_tool.name, aios_tool.description, aios_tool.input_schema)(handler)
