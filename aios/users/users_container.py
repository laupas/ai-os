from dependency_injector import containers, providers

from aios.users.authorizer import Authorizer
from aios.users.default_roles import DefaultRoles
from aios.users.owner_bootstrapper import OwnerBootstrapper


class UsersContainer(containers.DeclarativeContainer):
    users = providers.Dependency()
    roles = providers.Dependency()
    owner = providers.Dependency(default=None)
    ids = providers.Dependency()

    authorizer = providers.Singleton(Authorizer, roles=roles)
    default_roles = providers.Singleton(DefaultRoles)
    bootstrapper = providers.Singleton(
        OwnerBootstrapper,
        users=users,
        roles=roles,
        default_roles=default_roles,
        owner=owner,
        ids=ids,
    )
