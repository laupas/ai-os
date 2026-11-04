from pathlib import Path

from aios.config_repo.front_matter_layout import FrontMatterLayout
from aios.config_repo.git_document_store import GitDocumentStore
from aios.config_repo.git_repository import GitRepository
from aios.config_repo.yaml_layout import YamlLayout
from aios.entities.agents.agent import Agent
from aios.entities.connectors.connector import Connector
from aios.entities.schedules.schedule import Schedule
from aios.entities.skills.skill import Skill
from aios.entities.users.role import Role
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.json_file_document_store import JsonFileDocumentStore


class RepoWorld:
    """A configuration repository in a temp dir, laid out as ai-os lays it out,
    with the four collections on top. The repository is not created yet."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "config"
        self.repo = GitRepository(self.root)
        self.legacy = JsonFileDocumentStore(tmp_path / "data")
        self.store = GitDocumentStore(
            self.repo,
            {
                "agents": FrontMatterLayout("agents/{id}.md", "prompt"),
                "skills": FrontMatterLayout("skills/{id}/SKILL.md", "content", name_in_head=True),
                "connectors": YamlLayout("connectors"),
                "schedules": YamlLayout("schedules"),
                "roles": YamlLayout("roles"),
            },
            self.legacy,
            {"schedules": ["last_fired_at"]},
        )
        self.agents: Collection[Agent] = self._collection("agents", Agent)
        self.skills: Collection[Skill] = self._collection("skills", Skill)
        self.connectors: Collection[Connector] = self._collection("connectors", Connector)
        self.schedules: Collection[Schedule] = self._collection("schedules", Schedule)
        self.roles: Collection[Role] = self._collection("roles", Role)

    @property
    def collections(self) -> list[Collection]:  # type: ignore[type-arg]
        return [self.agents, self.skills, self.connectors, self.schedules]

    def log(self, path: str) -> list[dict[str, str]]:
        return self.repo.log(path)

    def _collection(self, name: str, entity: type) -> Collection:  # type: ignore[type-arg]
        return Collection(CollectionDefinition(name=name, entity=entity), self.store)
