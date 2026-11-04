from dependency_injector import containers, providers

from aios.conversations.conversation_delivery import ConversationDelivery
from aios.conversations.gateway import Gateway


class GatewayContainer(containers.DeclarativeContainer):
    users = providers.Dependency()
    authorizer = providers.Dependency()
    resolver = providers.Dependency()
    recorder = providers.Dependency()
    locks = providers.Dependency()
    canceller = providers.Dependency()
    engine = providers.Dependency()
    channels = providers.Dependency()
    approvals = providers.Dependency()
    observers = providers.Dependency(default=[])

    delivery = providers.Singleton(ConversationDelivery, channels=channels)
    gateway = providers.Singleton(
        Gateway,
        users=users,
        authorizer=authorizer,
        resolver=resolver,
        recorder=recorder,
        locks=locks,
        canceller=canceller,
        engine=engine,
        channels=channels,
        approvals=approvals,
        observers=observers,
        delivery=delivery,
    )
