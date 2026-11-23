from dependency_injector import containers, providers

from aios.store.store_installer import StoreInstaller
from aios.store.store_installs import StoreInstalls
from aios.store.store_source_reader import StoreSourceReader
from aios.store.store_sources import StoreSources


class StoreContainer(containers.DeclarativeContainer):
    """The Store: sources to install agents, skills, connectors and triggers from."""

    root = providers.Dependency()  # where the sources are checked out
    sources = providers.Dependency()  # a getter: the sources in aios.yaml now
    config_store = providers.Dependency()
    agents = providers.Dependency()
    skills = providers.Dependency()
    connectors = providers.Dependency()
    triggers = providers.Dependency()
    variables = providers.Dependency()
    ids = providers.Dependency()
    clock = providers.Dependency()
    secrets = providers.Dependency(default=None)

    catalog = providers.Singleton(
        StoreSources, root=root, sources=sources, reader=providers.Singleton(StoreSourceReader)
    )
    installer = providers.Singleton(
        StoreInstaller,
        config_store=config_store,
        agents=agents,
        skills=skills,
        connectors=connectors,
        triggers=triggers,
        variables=variables,
        ids=ids,
        clock=clock,
        installs=providers.Singleton(StoreInstalls, config_store=config_store, clock=clock),
        secrets=secrets,
    )
