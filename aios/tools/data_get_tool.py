from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class DataGetTool(AiosTool):
    def __init__(self, guard: CollectionAccessGuard) -> None:
        self._guard = guard

    @property
    def name(self) -> str:
        return "data_get"

    @property
    def description(self) -> str:
        return "Read one document of a collection by id."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"collection": {"type": "string"}, "id": {"type": "string"}},
            "required": ["collection", "id"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        collection = self._guard.readable(str(args["collection"]))
        item = self._guard.get_visible(collection, str(args["id"]), context.user.id)
        if item is None:
            raise ToolError(f"No document {args['id']!r} in {collection.name}.")
        return item.model_dump_json()
