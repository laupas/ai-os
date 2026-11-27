from aios.channels.message_channel import MessageChannel
from aios.conversations.artifact_presenter import ArtifactPresenter
from aios.entities.artifacts.artifact import Artifact
from aios.entities.conversations.channel_binding import ChannelBinding


class LinkArtifactPresenter(ArtifactPresenter):
    """Fallback for channels that cannot take a file: names the artifact and links
    to its conversation in the web console, where it opens after signing in."""

    def __init__(self, channel: MessageChannel) -> None:
        self._channel = channel

    async def show_artifact(
        self, binding: ChannelBinding, artifact: Artifact, link: str | None
    ) -> None:
        where = link or "the chat in the web console"
        await self._channel.send(binding, f"📄 **{artifact.title}**: open it in {where}")
