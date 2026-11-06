from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class DataDeleteTool(AiosTool):
    """Deletes a document. Approval is asked by `DataAccessApprovalRule`."""

    NAME = "data_delete"

    def __init__(self, guard: CollectionAccessGuard) -> None:
        self._guard = guard

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return "Delete one document of a collection by id."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"collection": {"type": "string"}, "id": {"type": "string"}},
            "required": ["collection", "id"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        collection = self._guard.writable(str(args["collection"]))
        doc_id = str(args["id"])
        if self._guard.get_visible(collection, doc_id, context.user.id) is None:
            raise ToolError(f"No document {doc_id!r} in {collection.name}.")
        await collection.delete(doc_id)
        return f"Deleted {collection.name}/{doc_id}."
