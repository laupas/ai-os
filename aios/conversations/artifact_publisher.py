import logging

from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.conversations.artifact_presenter_resolver import ArtifactPresenterResolver
from aios.conversations.artifact_store import ArtifactStore
from aios.conversations.message_recorder import MessageRecorder
from aios.entities.artifacts.artifact import Artifact
from aios.entities.artifacts.artifact_format import ArtifactFormat
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.conversations.message_role import MessageRole
from aios.entities.users.user import User
from aios.storage.collection import Collection

log = logging.getLogger(__name__)


class ArtifactPublisher:
    """Keeps an artifact with its conversation and shows it wherever the
    conversation lives.

    The `artifact` message it records is what the web console shows as a card;
    every other binding gets it from its channel's `ArtifactPresenter`: a file on
    Slack, a link elsewhere. One place failing never stops the others.
    """

    def __init__(
        self,
        store: ArtifactStore,
        recorder: MessageRecorder,
        conversations: Collection[Conversation],
        presenters: ArtifactPresenterResolver,
        clock: Clock,
        ids: IdGenerator,
        public_url: str | None = None,
    ) -> None:
        self._store = store
        self._recorder = recorder
        self._conversations = conversations
        self._presenters = presenters
        self._clock = clock
        self._ids = ids
        self._public_url = public_url

    async def publish(
        self,
        conversation_id: str,
        user: User,
        origin: ChannelBinding,
        title: str,
        format: ArtifactFormat,
        content: str,
    ) -> Artifact:
        artifact = Artifact(
            id=self._ids.new_id(),
            conversation_id=conversation_id,
            user_id=user.id,
            title=title,
            format=format,
            content=content,
            created_at=self._clock.now(),
        )
        await self._store.put(artifact)
        await self._recorder.record(
            conversation_id,
            MessageRole.ARTIFACT,
            title,
            origin.channel,
            artifact=artifact.ref(),
        )
        link = self.link(conversation_id)
        for binding in self._bindings(conversation_id, origin):
            try:
                presenter = self._presenters.artifact_presenter_for(binding.channel)
                await presenter.show_artifact(binding, artifact, link)
            except KeyError:
                continue  # a channel that is not enabled any more
            except Exception:
                log.exception("could not show artifact %s on %s", artifact.id, binding.channel)
        return artifact

    def link(self, conversation_id: str) -> str | None:
        if not self._public_url:
            return None
        return f"{self._public_url.rstrip('/')}/#/chat/{conversation_id}"

    def _bindings(self, conversation_id: str, origin: ChannelBinding) -> list[ChannelBinding]:
        conversation = self._conversations.get(conversation_id)
        return conversation.bindings if conversation is not None else [origin]
