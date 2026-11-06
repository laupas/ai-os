import logging
import re

from aios.bootstrap.startup_step import StartupStep
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.storage.collection import Collection

log = logging.getLogger(__name__)

OLD = {"crypto_signal": "signal", "crypto_quote": "quote", "crypto_trade": "trade",
       "crypto_balance": "balance"}  # fmt: skip
HISTORY = "Past orders are in the `trades` collection (`data_query`)."
CONFIGURATOR = (
    "  `read_logs` and the `crypto_*` tools. The `config_*` tools work for you alone; do",
    "  `read_logs`. Code connectors (such as `crypto`) are connectors of their own. The\n"
    "  `config_*` tools work for you alone; do",
)


class CryptoConnectorMigration(StartupStep):
    """Moves an installation from the built-in `crypto_*` tools (until 2026-11-06)
    to the code connector `crypto`: creates the connector, and moves every agent's
    grant and the tool names in its prompt. Does nothing once no agent has the old
    grants. The trading limits move by themselves, see `AppConfig`.

    Delete once every installation has started past it.
    """

    def __init__(self, agents: Collection[Agent], connectors: Collection[Connector]) -> None:
        self._agents = agents
        self._connectors = connectors

    async def run(self) -> None:
        moving = [a for a in self._agents.all() if self._old_tools(a)]
        if not moving:
            return
        if self._connectors.get("crypto") is None:
            await self._connectors.put(Connector(id="crypto", config={"code": "crypto"}))
            log.info("created the crypto code connector, which the crypto_* tools became")
        for agent in moving:
            await self._agents.put(self._moved(agent))
            log.info("moved agent %s to the crypto connector", agent.id)
        configurator = self._agents.get("ai-os-configurator")
        if configurator is not None and CONFIGURATOR[0] in configurator.prompt:
            prompt = configurator.prompt.replace(*CONFIGURATOR)
            await self._agents.put(configurator.model_copy(update={"prompt": prompt}))

    @staticmethod
    def _old_tools(agent: Agent) -> list[str]:
        return [t for t in agent.connectors.get("aios") or [] if t in OLD]

    def _moved(self, agent: Agent) -> Agent:
        old = self._old_tools(agent)
        aios = [t for t in agent.connectors.get("aios") or [] if t not in OLD]
        crypto = [OLD[t] for t in old]
        if "crypto_trade" in old:
            crypto.append("trades")
        connectors = {k: v for k, v in agent.connectors.items() if k != "aios"}
        if aios:
            connectors["aios"] = aios
        connectors["crypto"] = crypto
        prompt = agent.prompt.replace(HISTORY, "Past orders: `trades`.")
        for before, after in OLD.items():
            prompt = re.sub(rf"`{before}`", f"`{after}`", prompt)
        return agent.model_copy(update={"connectors": connectors, "prompt": prompt})
