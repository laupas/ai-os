import re
from typing import Any

from pydantic import BaseModel, ValidationError

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.catalog_error import CatalogError
from aios.agents.skill_catalog import SkillCatalog
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connectors import CODE_KEY, CodeConnectors
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.skills.skill import Skill
from aios.storage.collection import Collection
from aios.tools.tool_error import ToolError
from aios.variables.secret_extractor import SecretExtractor

CONNECTOR_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


class ConfigEditor:
    """Agents, skills and connectors for the `config_*` tools. Saves go through the
    same checks as the console: names, fixed agents, the built-in connector.

    These collections stay closed to the `data_*` tools; who may use this is decided
    by `ConfigChangeApprovalRule`.

    The settings a code connector's manifest locks are out of reach here, even with
    an administrator's approval: an agent cannot change them, nor add, delete or
    repoint a connector that has them (it would come back with the defaults).
    """

    KINDS = ("agents", "skills", "connectors")

    def __init__(
        self,
        agents: AgentCatalog,
        skills: SkillCatalog,
        connectors: Collection[Connector],
        secrets: SecretExtractor | None = None,
        code: CodeConnectorLibrary | None = None,
    ) -> None:
        self._code = code
        self._secrets = secrets
        self._agents = agents
        self._skills = skills
        self._connectors = connectors

    def list(self, kind: str) -> list[dict[str, Any]]:
        items: list[BaseModel] = {
            "agents": self._agents.all,
            "skills": self._skills.all,
            "connectors": lambda: sorted(self._connectors.all(), key=lambda c: c.id),
        }[self._kind(kind)]()
        return [item.model_dump(mode="json") for item in items]

    def get(self, kind: str, name: str) -> dict[str, Any]:
        item: BaseModel | None = {
            "agents": self._agents.get,
            "skills": self._skills.get,
            "connectors": self._connectors.get,
        }[self._kind(kind)](name)
        if item is None:
            raise ToolError(f"There is no {kind} entry called {name!r}.")
        return item.model_dump(mode="json")

    async def save(self, kind: str, document: dict[str, Any]) -> str:
        kind = self._kind(kind)
        try:
            if kind == "agents":
                await self._agents.save(Agent.model_validate(document))
            elif kind == "skills":
                await self._skills.save(Skill.model_validate(document))
            else:
                await self._save_connector(Connector.model_validate(document))
        except ValidationError as exc:
            raise ToolError(f"The document does not fit {kind}: {exc}") from exc
        except CatalogError as exc:
            raise ToolError(str(exc)) from exc
        return f"Saved {kind}/{document['id']}."

    async def delete(self, kind: str, name: str) -> str:
        self.get(kind, name)
        try:
            if kind == "agents":
                await self._agents.delete(name)
            elif kind == "skills":
                await self._skills.delete(name)
            else:
                existing = self._connectors.get(name)
                if existing is not None and self._locked(existing):
                    raise CatalogError(f"{name} has locked settings: delete it in the console")
                await self._connectors.delete(name)
        except CatalogError as exc:
            raise ToolError(str(exc)) from exc
        return f"Deleted {kind}/{name}."

    async def _save_connector(self, connector: Connector) -> None:
        if connector.id == ConnectorCatalog.BUILTIN:
            raise CatalogError("the built-in aios connector cannot be changed")
        if not CONNECTOR_NAME.match(connector.id):
            raise CatalogError("a connector name is lower-case letters, digits, - and _")
        self._check_locks(connector, self._connectors.get(connector.id))
        if self._secrets is not None:
            config, _ = await self._secrets.extract(connector.id, connector.config, "ai-os")
            connector = connector.model_copy(update={"config": config})
        await self._connectors.put(connector)

    def _check_locks(self, new: Connector, old: Connector | None) -> None:
        locked = self._locked(new) | (self._locked(old) if old else set())
        if not locked:
            return
        if old is None or old.config.get(CODE_KEY) != new.config.get(CODE_KEY):
            raise CatalogError(
                f"{new.id} runs a code connector with locked settings: add or change it "
                "in the console"
            )
        before, after = CodeConnectors.stored(old), CodeConnectors.stored(new)
        changed = sorted(k for k in locked if before.get(k) != after.get(k))
        if changed:
            raise CatalogError(
                f"locked, changed only in the console by an administrator: {', '.join(changed)}"
            )

    def _locked(self, connector: Connector) -> set[str]:
        name = connector.config.get(CODE_KEY)
        if self._code is None or not isinstance(name, str):
            return set()
        manifest = self._code.get(name)
        if manifest is None:
            # Unreadable for now: its locks cannot be known, so nothing may change.
            raise CatalogError(f"code connector {name} cannot be read: change it in the console")
        return manifest.locked()

    def _kind(self, kind: str) -> str:
        if kind not in self.KINDS:
            raise ToolError(f"kind is one of {', '.join(self.KINDS)}, not {kind!r}.")
        return kind
