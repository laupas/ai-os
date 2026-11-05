from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.config_editor import ConfigEditor
from aios.tools.tool_context import ToolContext


class ConfigPutTool(AiosTool):
    """Creates or replaces an agent, skill or connector. Approval is asked by
    `ConfigChangeApprovalRule`."""

    NAME = "config_put"

    def __init__(self, editor: ConfigEditor) -> None:
        self._editor = editor

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Create or replace an agent, skill or connector of ai-os. `document.id` is its "
            "name. This replaces the whole document: read the current one first when "
            "changing it. Every save asks an administrator for approval."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(ConfigEditor.KINDS)},
                "document": {"type": "object"},
            },
            "required": ["kind", "document"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        return await self._editor.save(str(args["kind"]), dict(args["document"]))
