from dependency_injector import containers, providers

from aios.config.app_config_loader import AppConfigLoader
from aios.config.live_app_config import LiveAppConfig
from aios.config.settings import Settings


class ConfigContainer(containers.DeclarativeContainer):
    """`app_config` is aios.yaml as ai-os started; the section getters below give
    it as it is now, for what applies without a restart."""

    settings = providers.Singleton(Settings)
    loader = providers.Singleton(
        AppConfigLoader, path=settings.provided.resolved_config_file.call()
    )
    live = providers.Singleton(LiveAppConfig, config=loader.provided.load.call())
    app_config = providers.Singleton(live.provided.started_with.call())

    agent = providers.Callable(lambda live: lambda: live.current().agent, live)
    approval = providers.Callable(lambda live: lambda: live.current().approval, live)
    files = providers.Callable(lambda live: lambda: live.current().files, live)
    scheduler = providers.Callable(lambda live: lambda: live.current().scheduler, live)
    timezone = providers.Callable(lambda live: lambda: live.current().timezone, live)
