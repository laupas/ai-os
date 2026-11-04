from dependency_injector import containers, providers

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

    resolver = providers.Singleton(
        ConversationResolver, conversations=conversations, clock=clock, ids=ids
    )
    recorder = providers.Singleton(
        MessageRecorder, log=append_log, clock=clock, ids=ids, observers=observers
    )
    locks = providers.Singleton(ConversationLockManager)
    canceller = providers.Singleton(TurnCanceller)
    deleter = providers.Singleton(
        ConversationDeleter, conversations=conversations, recorder=recorder, canceller=canceller
    )
