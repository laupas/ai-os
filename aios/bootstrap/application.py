import asyncio
import logging

from aios.approvals.approval_service import ApprovalService
from aios.bootstrap.background_service import BackgroundService
from aios.bootstrap.startup_notice import StartupNotice
from aios.bootstrap.startup_step import StartupStep
from aios.channels.channel_directory import ChannelDirectory
from aios.conversations.gateway import Gateway
from aios.storage.collection_registry import CollectionRegistry

log = logging.getLogger(__name__)


class Application:
    """Loads the data, then runs every enabled channel and background service until
    one of them stops."""

    def __init__(
        self,
        registry: CollectionRegistry,
        startup: list[StartupStep],
        approvals: ApprovalService,
        channels: ChannelDirectory,
        gateway: Gateway,
        background: list[BackgroundService],
        notice: StartupNotice,
    ) -> None:
        self._registry = registry
        self._startup = startup
        self._approvals = approvals
        self._channels = channels
        self._gateway = gateway
        self._background = background
        self._notice = notice

    async def run(self) -> None:
        await self._registry.load_all()
        for step in self._startup:  # in order: each may rely on the ones before
            await step.run()
        await self._approvals.expire_pending()
        channels = self._channels.enabled()
        if not channels:
            raise RuntimeError("no channels enabled in config")
        log.info("starting channels: %s", ", ".join(c.name for c in channels))
        tasks = [asyncio.create_task(c.start(self._gateway, self._approvals)) for c in channels]
        tasks += [asyncio.create_task(service.run()) for service in self._background]
        # Not among `tasks`: it finishes on its own, and the first task to finish
        # ends the application.
        notice = asyncio.create_task(self._notice.run())
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in [*pending, notice]:
            task.cancel()
        for task in done:
            task.result()
