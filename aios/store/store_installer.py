import asyncio
from pathlib import Path

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.catalog_error import CatalogError
from aios.agents.repo_agent_reader import RepoAgentReader
from aios.agents.skill_catalog import SkillCatalog
from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.config_repo.git_document_store import GitDocumentStore
from aios.connectors.code_connectors import CODE_KEY
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.skills.skill import Skill
from aios.entities.store.store_install_record import StoreInstallRecord
from aios.entities.triggers.trigger import Trigger
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.store.store_error import StoreError
from aios.store.store_install_result import StoreInstallResult
from aios.store.store_installs import StoreInstalls
from aios.store.store_item import StoreItem
from aios.store.store_kind import StoreKind
from aios.store.store_listing import StoreListing
from aios.store.store_plan import StorePlan
from aios.store.store_ref import StoreRef
from aios.store.store_uninstall_result import StoreUninstallResult
from aios.store.store_version import StoreVersion
from aios.variables.secret_extractor import SecretExtractor
from aios.variables.variable_catalog import VariableCatalog

MAX_CODE_FILE = 1024**2
SKIPPED = {"__pycache__", ".git", ".venv", "node_modules"}


class StoreInstaller:
    """Installs a store item into the configuration repository, with whatever it
    requires that the installation does not have yet, in one commit.

    Everything goes through the same checks as a save in the console: agents and
    skills through their catalogs, a connector's config through `SecretExtractor`.
    What is installed already is never overwritten as a requirement; the item
    itself only with `replace`. A trigger is the installing user's, under a new id.
    A code connector's folder is copied into `code/` only with `trust_code`: it is
    a program that will run on this server.
    """

    def __init__(
        self,
        config_store: GitDocumentStore,
        agents: AgentCatalog,
        skills: SkillCatalog,
        connectors: Collection[Connector],
        triggers: Collection[Trigger],
        variables: VariableCatalog,
        ids: IdGenerator,
        clock: Clock,
        installs: StoreInstalls,
        secrets: SecretExtractor | None = None,
    ) -> None:
        self._installs = installs
        self._store = config_store
        self._agents = agents
        self._skills = skills
        self._connectors = connectors
        self._triggers = triggers
        self._variables = variables
        self._ids = ids
        self._clock = clock
        self._secrets = secrets

    def installed(self, item: StoreItem) -> bool:
        return self._has(item.kind, item.id)

    def record_of(self, item: StoreItem) -> StoreInstallRecord | None:
        """Where the installed item came from; None if it is not installed, or was
        not installed from the Store."""
        return self._installs.get(item.ref) if self.installed(item) else None

    def update_available(self, item: StoreItem) -> bool:
        record = self.record_of(item)
        return (
            record is not None
            and record.source == item.source
            and StoreVersion.newer(item.meta.version, record.version)
        )

    def plan(self, listing: StoreListing, item: StoreItem) -> StorePlan:
        install: list[StoreItem] = []
        kept, missing = [], []
        seen = {item.ref}
        todo = list(item.requires())
        while todo:
            ref = todo.pop(0)
            if ref in seen:
                continue
            seen.add(ref)
            found = listing.get(ref)
            if self._has(ref.kind, ref.id):
                kept.append(ref)
            elif found is None:
                missing.append(ref)
            else:
                install.insert(0, found)
                todo.extend(found.requires())
        install.append(item)
        fields = {f.variable: f for i in install for f in i.meta.variables}
        return StorePlan(
            item=item, install=install, kept=kept, missing=missing, variables=list(fields.values())
        )

    async def install(
        self,
        plan: StorePlan,
        user: User,
        values: dict[str, str],
        replace: bool = False,
        trust_code: bool = False,
    ) -> StoreInstallResult:
        item = plan.item
        if self.installed(item) and not replace:
            raise StoreError(f"{item.kind.value} {item.id} is installed already", conflict=True)
        if plan.code and not trust_code:
            raise StoreError("this installs a code connector: a program that runs on this server")
        files = {
            i.code_name: await asyncio.to_thread(self._code_files, i)
            for i in plan.install
            if i.code_folder is not None
        }
        await self._save_variables(plan, values, user)
        result = StoreInstallResult(
            kept=[str(r) for r in plan.kept],
            missing=[str(r) for r in plan.missing],
            version=item.meta.version,
        )
        async with self._store.batch(f"Store: install {item.kind.value} {item.id}"):
            for name, folder in files.items():
                for path, text in folder.items():
                    await self._store.write_file(f"code/{name}/{path}", text, "")
            for each in plan.install:
                result.moved_secrets += await self._put(each, user)
                result.installed.append(str(each.ref))
            for each in plan.install:
                if each.code_folder is not None:
                    result.installed += await self._code_agents(each.code_folder)
            # A trigger is added anew each time: there is nothing to update.
            await self._installs.record(
                [i for i in plan.install if i.kind is not StoreKind.TRIGGER], user
            )
        return result

    def used_by(self, ref: StoreRef) -> list[str]:
        """What refers to an installed item: agents granted a connector or a skill,
        triggers that run an agent."""
        match ref.kind:
            case StoreKind.CONNECTOR:
                return [f"agent:{a.id}" for a in self._agents.all() if ref.id in a.connectors]
            case StoreKind.SKILL:
                return [f"agent:{a.id}" for a in self._agents.all() if ref.id in a.skills]
            case StoreKind.AGENT:
                return [f"trigger:{t.id}" for t in self._triggers.all() if t.agent == ref.id]
            case _:
                return []

    async def uninstall(self, ref: StoreRef) -> StoreUninstallResult:
        """Removes one installed item and its record, in one commit; for a code
        connector also its folder. What it brought along, its Variables and its
        sign-ins stay: other items may use them."""
        if ref.kind is StoreKind.TRIGGER:
            raise StoreError("a trigger is deleted on the Triggers page")
        if not self._has(ref.kind, ref.id):
            raise StoreError(f"{ref.kind.value} {ref.id} is not installed")
        if ref.kind is StoreKind.AGENT and self._agents.is_fixed(ref.id):
            raise StoreError(f"{ref.id} is part of ai-os and cannot be removed")
        result = StoreUninstallResult(still_used_by=self.used_by(ref))
        async with self._store.batch(f"Store: uninstall {ref.kind.value} {ref.id}"):
            code = None
            try:
                match ref.kind:
                    case StoreKind.AGENT:
                        await self._agents.delete(ref.id)
                    case StoreKind.SKILL:
                        await self._skills.delete(ref.id)
                    case StoreKind.CONNECTOR:
                        connector = self._connectors.get(ref.id)
                        code = connector.config.get(CODE_KEY) if connector else None
                        await self._connectors.delete(ref.id)
            except CatalogError as exc:
                raise StoreError(str(exc)) from exc
            result.removed.append(str(ref))
            if isinstance(code, str) and not self._code_in_use(code):
                folder = f"code/{code}"
                result.removed += await self._store.remove_folder(folder, "")
            await self._installs.forget([ref])
        return result

    def _code_in_use(self, name: str) -> bool:
        """Whether another connector still runs this code."""
        return any(c.config.get(CODE_KEY) == name for c in self._connectors.all())

    async def _put(self, item: StoreItem, user: User) -> list[str]:
        try:
            match item.kind:
                case StoreKind.AGENT:
                    await self._agents.save(Agent.model_validate(item.document))
                case StoreKind.SKILL:
                    await self._skills.save(Skill.model_validate(item.document))
                case StoreKind.CONNECTOR:
                    return await self._put_connector(Connector.model_validate(item.document), user)
                case StoreKind.TRIGGER:
                    trigger = {
                        **item.document,
                        "id": self._ids.new_id(),
                        "user_id": user.id,
                        "created_at": self._clock.now(),
                    }
                    await self._triggers.put(Trigger.model_validate(trigger))
        except (CatalogError, ValueError) as exc:
            raise StoreError(f"{item.kind.value} {item.id}: {exc}") from exc
        return []

    async def _put_connector(self, connector: Connector, user: User) -> list[str]:
        moved: list[str] = []
        if self._secrets is not None:
            config, moved = await self._secrets.extract(connector.id, connector.config, user.name)
            connector = connector.model_copy(update={"config": config})
        await self._connectors.put(connector)
        return moved

    async def _code_agents(self, folder: Path) -> list[str]:
        """The agents a code connector brings, as adding it in the console does."""
        added = []
        for agent in await asyncio.to_thread(RepoAgentReader(folder / "agents").read):
            if self._agents.get(agent.id) is None:
                await self._agents.save(agent)
                added.append(f"agent:{agent.id}")
        return added

    async def _save_variables(self, plan: StorePlan, values: dict[str, str], user: User) -> None:
        fields = {f.variable: f for f in plan.variables}
        typed = {k: v.strip() for k, v in values.items() if v.strip()}
        unknown = sorted(set(typed) - set(fields))
        if unknown:
            raise StoreError(f"{plan.item.id} asks for no {', '.join(unknown)}")
        for name, value in typed.items():
            field = fields[name]
            try:
                await self._variables.save(
                    name, value, field.secret, False, f"{plan.item.id}: {field.label}", user.name
                )
            except CatalogError as exc:
                raise StoreError(str(exc)) from exc

    def _has(self, kind: StoreKind, item_id: str) -> bool:
        match kind:
            case StoreKind.AGENT:
                return self._agents.get(item_id) is not None
            case StoreKind.SKILL:
                return self._skills.get(item_id) is not None
            case StoreKind.CONNECTOR:
                return self._connectors.get(item_id) is not None
            case StoreKind.TRIGGER:
                return False  # each install adds one

    @staticmethod
    def _code_files(item: StoreItem) -> dict[str, str]:
        """The code connector's files as text; anything else refuses the install."""
        assert item.code_folder is not None
        files = {}
        for file in sorted(item.code_folder.rglob("*")):
            relative = file.relative_to(item.code_folder)
            if not file.is_file() or SKIPPED & set(relative.parts) or file.suffix == ".pyc":
                continue
            if file.is_symlink() or file.stat().st_size > MAX_CODE_FILE:
                raise StoreError(f"code/{item.code_name}/{relative}: not a plain file under 1 MiB")
            try:
                files[relative.as_posix()] = file.read_text("utf-8")
            except UnicodeDecodeError as exc:
                raise StoreError(f"code/{item.code_name}/{relative}: not a text file") from exc
        return files
