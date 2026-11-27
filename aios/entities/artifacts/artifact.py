import re
from datetime import datetime

from pydantic import BaseModel

from aios.entities.artifacts.artifact_format import ArtifactFormat
from aios.entities.artifacts.artifact_ref import ArtifactRef

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class Artifact(BaseModel):
    """A document an agent made in a conversation, such as a report of a run.

    It belongs to its conversation: whoever may read the conversation may open it,
    and it is deleted with it.
    """

    id: str
    conversation_id: str
    user_id: str
    title: str
    format: ArtifactFormat
    content: str
    created_at: datetime

    @property
    def file_name(self) -> str:
        stem = _UNSAFE.sub("-", self.title).strip("-.")[:80] or "artifact"
        return f"{stem}.{self.format.extension}"

    def ref(self) -> ArtifactRef:
        return ArtifactRef(id=self.id, title=self.title, format=self.format)
