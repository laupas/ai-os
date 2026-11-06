from aios.bootstrap.startup_step import StartupStep
from aios.connectors.connector_tokens import ConnectorTokens


class ConnectorTokenMigration(StartupStep):
    """Brings stored connector sign-ins to the current form: one per connector and
    account, encrypted. Does nothing once they are."""

    def __init__(self, tokens: ConnectorTokens) -> None:
        self._tokens = tokens

    async def run(self) -> None:
        await self._tokens.migrate()
