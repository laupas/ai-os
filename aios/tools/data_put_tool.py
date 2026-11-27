from typing import Any

from pydantic import ValidationError

from aios.common.id_generator import IdGenerator
from aios.tools.aios_tool import AiosTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.document_stamp import DocumentStamp
from aios.tools.tool_context import ToolContext
from aios.tools.tool_error import ToolError


class DataPutTool(AiosTool):
    """Creates or replaces a document. Approval is asked by `DataAccessApprovalRule`.
    A collection's `DocumentStamp`, if it has one, sets the fields ai-os owns."""

    NAME = "data_put"

    def __init__(
        self,
        guard: CollectionAccessGuard,
        ids: IdGenerator,
        stamps: list[DocumentStamp] | None = None,
    ) -> None:
        self._guard = guard
        self._ids = ids
        self._stamps = {s.collection: s for s in stamps or []}

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Create or replace a document in a collection. Without an `id` a new one is "
            "created. The document must match the collection's schema; read the current "
            "document first when changing one, since this replaces it whole. In a "
            "collection with an owner field (`user_id`), leave it out to save the document "
            "for the current user; set it to null to share it with every user, which an "
            "administrator must approve."
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
        definition = collection.definition
        existing = collection.get(str(document["id"]))
        if definition.owner_field is not None:
            document.setdefault(definition.owner_field, context.user.id)
            if existing is not None and not definition.visible_to(existing, context.user.id):
                raise ToolError(f"No document {document['id']!r} in {collection.name}.")
        try:
            item = collection.parse(document)
        except ValidationError as exc:
            raise ToolError(f"The document does not fit {collection.name}: {exc}") from exc
        stamp = self._stamps.get(collection.name)
        if stamp is not None:
            item = stamp.stamp(item, existing, context)
        if not definition.visible_to(item, context.user.id):
            raise ToolError(
                f"A document in {collection.name} belongs to the current user or is shared."
            )
        await collection.put(item)
        return f"Saved {collection.name}/{document['id']}."
