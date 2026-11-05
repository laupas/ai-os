import json
from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.config_editor import ConfigEditor
from aios.tools.tool_context import ToolContext


class ConfigListTool(AiosTool):
    NAME = "config_list"

    def __init__(self, editor: ConfigEditor) -> None:
        self._editor = editor

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return "List every agent, skill or connector of ai-os, with all its fields."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": list(ConfigEditor.KINDS)}},
            "required": ["kind"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        return json.dumps(self._editor.list(str(args["kind"])), ensure_ascii=False)
