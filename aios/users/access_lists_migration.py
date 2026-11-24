import logging

import yaml

from aios.bootstrap.startup_step import StartupStep
from aios.config_repo.git_document_store import GitDocumentStore
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.users.audience_entry import EVERYONE
from aios.storage.collection import Collection

log = logging.getLogger(__name__)

MIGRATIONS = ".aios-migrations.yaml"
NAME = "access-lists"


class AccessListsMigration(StartupStep):
    """Once per configuration repository: agents and connectors from before access
    lists were available to everyone, and stay so (`available_to: [everyone]`),
    since no list now means administrators only. A repository whose items already
    carry lists (a new one, seeded with them) is only marked as done. The mark is
    in the repository, so a clone or a branch knows whether it was migrated."""

    def __init__(
        self,
        store: GitDocumentStore,
        agents: Collection[Agent],
        connectors: Collection[Connector],
    ) -> None:
        self._store = store
        self._agents = agents
        self._connectors = connectors

    async def run(self) -> None:
        done = self._done()
        if NAME in done:
            return
        agents, connectors = self._agents.all(), self._connectors.all()
        fresh = any(i.available_to is not None for i in [*agents, *connectors])
        async with self._store.batch("Access lists: what existed stays available to everyone"):
            if not fresh:
                for agent in agents:
                    await self._agents.put(agent.model_copy(update={"available_to": [EVERYONE]}))
                for connector in connectors:
                    await self._connectors.put(
                        connector.model_copy(update={"available_to": [EVERYONE]})
                    )
                log.info(
                    "access lists: %d agents and %d connectors stay available to everyone",
                    len(agents),
                    len(connectors),
                )
            text = yaml.safe_dump(sorted([*done, NAME]), allow_unicode=True)
            await self._store.write_file(MIGRATIONS, text, "")

    def _done(self) -> list[str]:
        try:
            data = yaml.safe_load(self._store.read_file(MIGRATIONS) or "") or []
        except yaml.YAMLError:
            return []
        return [str(d) for d in data] if isinstance(data, list) else []
