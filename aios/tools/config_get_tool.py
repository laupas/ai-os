import json
from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.config_editor import ConfigEditor
from aios.tools.tool_context import ToolContext


class ConfigGetTool(AiosTool):
    NAME = "config_get"

    def __init__(self, editor: ConfigEditor) -> None:
        self._editor = editor

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return "Read one agent, skill or connector of ai-os by name."

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
        document = self._editor.get(str(args["kind"]), str(args["name"]))
        return json.dumps(document, ensure_ascii=False)
