import asyncio
import logging

from aios.bootstrap.background_service import BackgroundService
from aios.connectors.connector_authorizer import ConnectorAuthorizer

log = logging.getLogger(__name__)


class ConnectorTokenRenewer(BackgroundService):
    """Renews connector sign-ins before they expire, so a turn never starts with
    an expired token."""

    def __init__(self, authorizer: ConnectorAuthorizer, interval_seconds: float = 300) -> None:
        self._authorizer = authorizer
        self._interval = interval_seconds

    async def run(self) -> None:
        while True:
            try:
                await self._authorizer.renew_due()
            except Exception:
                log.exception("renewing connector sign-ins failed")
            await asyncio.sleep(self._interval)
