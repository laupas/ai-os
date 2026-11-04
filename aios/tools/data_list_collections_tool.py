import json
from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.tool_context import ToolContext


class DataListCollectionsTool(AiosTool):
    def __init__(self, guard: CollectionAccessGuard) -> None:
        self._guard = guard

    @property
    def name(self) -> str:
        return "data_list_collections"

    @property
    def description(self) -> str:
        return "List the stored collections you may use, with their access and fields."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        summary = []
        for name in self._guard.readable_names():
            collection = self._guard.readable(name)
            summary.append(
                {
                    "name": name,
                    "access": collection.definition.agent_access.value,
                    "writes_need_approval": collection.definition.agent_writes_need_approval,
                    "count": len(collection.all()),
                    "schema": collection.definition.entity.model_json_schema(),
                }
            )
        return json.dumps(summary, ensure_ascii=False)
