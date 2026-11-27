from aios.entities.artifacts.artifact import Artifact
from aios.storage.document_store import DocumentStore

COLLECTION = "artifacts"


class ArtifactStore:
    """Artifacts by id, one document each in the data dir.

    Not a `Collection`: their content can be large, so it is read when asked for
    and never held in memory. The messages that present them (`Message.artifact`)
    are their index.
    """

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def put(self, artifact: Artifact) -> None:
        await self._store.put(COLLECTION, artifact.id, artifact.model_dump(mode="json"))

    async def get(self, artifact_id: str) -> Artifact | None:
        try:
            document = await self._store.get(COLLECTION, artifact_id)
        except ValueError:
            return None  # not an id we could have made
        return Artifact.model_validate(document) if document is not None else None

    async def delete(self, artifact_id: str) -> None:
        await self._store.delete(COLLECTION, artifact_id)
