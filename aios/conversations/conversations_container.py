from dependency_injector import containers, providers

from aios.conversations.artifact_publisher import ArtifactPublisher
from aios.conversations.artifact_store import ArtifactStore
from aios.conversations.conversation_deleter import ConversationDeleter
from aios.conversations.conversation_lock_manager import ConversationLockManager
from aios.conversations.conversation_resolver import ConversationResolver
from aios.conversations.message_recorder import MessageRecorder
from aios.conversations.turn_canceller import TurnCanceller


class ConversationsContainer(containers.DeclarativeContainer):
    """Conversation bookkeeping. The gateway is in `GatewayContainer`, because it
    needs the engine, which in turn needs the recorder from here."""

    conversations = providers.Dependency()
    append_log = providers.Dependency()
    clock = providers.Dependency()
    ids = providers.Dependency()
    observers = providers.Dependency(default=[])
    document_store = providers.Dependency()
    presenters = providers.Dependency()
    public_url = providers.Dependency(default=None)

    resolver = providers.Singleton(
        ConversationResolver, conversations=conversations, clock=clock, ids=ids
    )
    recorder = providers.Singleton(
        MessageRecorder, log=append_log, clock=clock, ids=ids, observers=observers
    )
    artifacts = providers.Singleton(ArtifactStore, store=document_store)
    publisher = providers.Singleton(
        ArtifactPublisher,
        store=artifacts,
        recorder=recorder,
        conversations=conversations,
        presenters=presenters,
        clock=clock,
        ids=ids,
        public_url=public_url,
    )
    locks = providers.Singleton(ConversationLockManager)
    canceller = providers.Singleton(TurnCanceller)
    deleter = providers.Singleton(
        ConversationDeleter,
        conversations=conversations,
        recorder=recorder,
        canceller=canceller,
        artifacts=artifacts,
    )
