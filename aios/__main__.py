import asyncio

from aios.bootstrap.application_container import ApplicationContainer
from aios.common.logging_setup import LoggingSetup
from aios.config.settings import Settings
from aios.config_repo.config_repo_bootstrap import ConfigRepoBootstrap


def main() -> None:
    settings = Settings()
    LoggingSetup(settings.log_level, settings.log_file()).configure()
    # Before the container: the configuration it loads may first have to be cloned.
    ConfigRepoBootstrap(settings).run()
    container = ApplicationContainer()
    try:
        asyncio.run(container.application().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
