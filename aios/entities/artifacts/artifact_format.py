from enum import StrEnum


class ArtifactFormat(StrEnum):
    """What an artifact is written in."""

    HTML = "html"
    MARKDOWN = "markdown"

    @property
    def extension(self) -> str:
        return {ArtifactFormat.HTML: "html", ArtifactFormat.MARKDOWN: "md"}[self]

    @property
    def mime_type(self) -> str:
        return {ArtifactFormat.HTML: "text/html", ArtifactFormat.MARKDOWN: "text/markdown"}[self]
