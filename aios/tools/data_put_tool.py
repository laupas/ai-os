from typing import Any

from pydantic import ValidationError

from aios.common.id_generator import IdGenerator
from aios.tools.aios_tool import AiosTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class DataPutTool(AiosTool):
    """Creates or replaces a document. Approval is asked by `DataAccessApprovalRule`."""

    NAME = "data_put"

    def __init__(self, guard: CollectionAccessGuard, ids: IdGenerator) -> None:
        self._guard = guard
        self._ids = ids

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Create or replace a document in a collection. Without an `id` a new one is "
            "created. The document must match the collection's schema; read the current "
            "document first when changing one, since this replaces it whole."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"collection": {"type": "string"}, "document": {"type": "object"}},
            "required": ["collection", "document"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        collection = self._guard.writable(str(args["collection"]))
        document = dict(args["document"])
        document.setdefault("id", self._ids.new_id())
        try:
            item = collection.parse(document)
        except ValidationError as exc:
            raise ToolError(f"The document does not fit {collection.name}: {exc}") from exc
        await collection.put(item)
        return f"Saved {collection.name}/{document['id']}."
