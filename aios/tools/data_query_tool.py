import json
from typing import Any

from aios.tools.aios_tool import AiosTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.tool_context import ToolContext

MAX_RESULTS = 50


class DataQueryTool(AiosTool):
    def __init__(self, guard: CollectionAccessGuard) -> None:
        self._guard = guard

    @property
    def name(self) -> str:
        return "data_query"

    @property
    def description(self) -> str:
        return (
            "List documents of a collection. `where` keeps only documents whose top-level "
            f"fields equal the given values. At most {MAX_RESULTS} results."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"collection": {"type": "string"}, "where": {"type": "object"}},
            "required": ["collection"],
        }

    async def run(self, args: dict[str, Any], context: ToolContext) -> str:
        collection = self._guard.readable(str(args["collection"]))
        where: dict[str, Any] = args.get("where") or {}
        documents = [item.model_dump(mode="json") for item in collection.all()]
        matches = [d for d in documents if all(d.get(k) == v for k, v in where.items())]
        return json.dumps(matches[:MAX_RESULTS], ensure_ascii=False)
