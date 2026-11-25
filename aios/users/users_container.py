from dependency_injector import containers, providers

from aios.users.authorizer import Authorizer
from aios.users.default_groups import DefaultGroups
from aios.users.owner_bootstrapper import OwnerBootstrapper
from aios.users.permission_audience import PermissionAudience
from aios.users.voice_gate import VoiceGate


class UsersContainer(containers.DeclarativeContainer):
    users = providers.Dependency()
    groups = providers.Dependency()
    owner = providers.Dependency(default=None)
    ids = providers.Dependency()

    authorizer = providers.Singleton(Authorizer, groups=groups)
    audience = providers.Singleton(PermissionAudience, authorizer=authorizer)
    voice_gate = providers.Singleton(VoiceGate, users=users, authorizer=authorizer)
    default_groups = providers.Singleton(DefaultGroups)
    bootstrapper = providers.Singleton(
        OwnerBootstrapper,
        users=users,
        groups=groups,
        default_groups=default_groups,
        owner=owner,
        ids=ids,
    )
