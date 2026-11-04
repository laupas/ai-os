from dependency_injector import containers, providers

from aios.config.app_config_loader import AppConfigLoader
from aios.config.settings import Settings


class ConfigContainer(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)
    loader = providers.Singleton(
        AppConfigLoader, path=settings.provided.resolved_config_file.call()
    )
    app_config = providers.Singleton(loader.provided.load.call())
