from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.config_editor import ConfigEditor
from aios.tools.tool_context import ToolContext


class ConfigDeleteTool(AiosTool):
    """Deletes an agent, skill or connector. Approval is asked by
    `ConfigChangeApprovalRule`."""

    NAME = "config_delete"

    def __init__(self, editor: ConfigEditor) -> None:
        self._editor = editor

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Delete an agent, skill or connector of ai-os by name. Fixed agents cannot be "
            "deleted. Asks an administrator for approval."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(ConfigEditor.KINDS)},
                "name": {"type": "string"},
            },
            "required": ["kind", "name"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        return await self._editor.delete(str(args["kind"]), str(args["name"]))
