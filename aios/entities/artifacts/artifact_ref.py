from pydantic import BaseModel

from aios.entities.artifacts.artifact_format import ArtifactFormat


class ArtifactRef(BaseModel):
    """An artifact as a message of its conversation points to it."""

    id: str
    title: str
    format: ArtifactFormat
