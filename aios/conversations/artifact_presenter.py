from abc import ABC, abstractmethod

from aios.entities.artifacts.artifact import Artifact
from aios.entities.conversations.channel_binding import ChannelBinding


class ArtifactPresenter(ABC):
    """Puts an artifact in front of the people of one binding: as a file, or as a
    link to the conversation in the web console (`link`, None when ai-os has no
    `web.public_url`). Optional for a channel: `LinkArtifactPresenter` is the
    fallback."""

    @abstractmethod
    async def show_artifact(
        self, binding: ChannelBinding, artifact: Artifact, link: str | None
    ) -> None: ...
