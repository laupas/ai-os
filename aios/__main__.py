import asyncio

from aios.bootstrap.application_container import ApplicationContainer
from aios.bootstrap.shutdown_watchdog import ShutdownWatchdog
from aios.common.logging_setup import LoggingSetup
from aios.config.settings import Settings
from aios.config_repo.config_repo_bootstrap import ConfigRepoBootstrap


async def run(container: ApplicationContainer) -> None:
    try:
        await container.application().run()
    finally:
        # Armed before asyncio's own cleanup, which can hang too.
        ShutdownWatchdog().arm()


def main() -> None:
    settings = Settings()
    LoggingSetup(settings.log_level, settings.log_file()).configure()
    # Before the container: the configuration it loads may first have to be cloned.
    ConfigRepoBootstrap(settings).run()
    container = ApplicationContainer()
    try:
        asyncio.run(run(container))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
