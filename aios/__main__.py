import asyncio
import logging

from aios.bootstrap.application_container import ApplicationContainer
from aios.bootstrap.shutdown_watchdog import ShutdownWatchdog
from aios.common.logging_setup import LoggingSetup
from aios.config.settings import Settings
from aios.config_repo.config_repo_bootstrap import ConfigRepoBootstrap
from aios.variables.secrets_key_missing import SecretsKeyMissing
from aios.variables.secrets_key_source import SecretsKeySource


async def run(container: ApplicationContainer) -> None:
    try:
        await container.application().run()
    finally:
        # Armed before asyncio's own cleanup, which can hang too.
        ShutdownWatchdog().arm()


def main() -> None:
    settings = Settings()
    LoggingSetup(settings.log_level, settings.log_file()).configure()
    # No start without the key: nothing else may generate one into the data dir.
    try:
        SecretsKeySource(
            settings.secrets_key, settings.secrets_key_previous, settings.secrets_key_file()
        ).current()
    except SecretsKeyMissing as exc:
        logging.getLogger("aios").critical("%s", exc)
        raise SystemExit(2) from exc
    # Before the container: the configuration it loads may first have to be cloned.
    ConfigRepoBootstrap(settings).run()
    container = ApplicationContainer()
    try:
        asyncio.run(run(container))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
