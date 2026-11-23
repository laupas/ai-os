from aios.config.app_config import AppConfig
from aios.config_repo.current_author import AIOS
from aios.storage.agent_access import AgentAccess
from aios.storage.collection_registry import CollectionRegistry
from aios.triggers.triggers_migration import TriggersMigration
from aios.web.aios_yaml_file import AiosYamlFile
from tests.config_repo.repo_world import RepoWorld

TRIGGER = "name: brief\nprompt: brief me\ncron:\n- 0 7 * * *\nuser_id: alice\n"
AIOS_YAML = (
    "timezone: Europe/Zurich\n"
    "# how often\n"
    "scheduler:\n  tick_seconds: 10\n"
    "collection_access:\n  schedules: read\n  roles: read\n"
)


def _older_repository(w: RepoWorld) -> None:
    w.repo.init()
    (w.root / "schedules").mkdir()
    (w.root / "schedules" / "s1.yaml").write_text(TRIGGER)
    (w.root / "agents").mkdir()
    (w.root / "agents" / "scheduler.md").write_text("---\ndescription: d\n---\nYou manage.\n")
    (w.root / "aios.yaml").write_text(AIOS_YAML)
    w.repo.commit(["schedules", "agents", "aios.yaml"], "before", AIOS)


def _migration(w: RepoWorld) -> TriggersMigration:
    return TriggersMigration(
        w.store, w.legacy, w.collections, AiosYamlFile(w.root / "aios.yaml", w.store)
    )


async def test_schedules_become_triggers_in_one_commit(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    _older_repository(w)
    await w.legacy.put(
        "schedules-state", "s1", {"id": "s1", "last_fired_at": "2026-11-20T07:00:00Z"}
    )

    await _migration(w).run()

    assert not (w.root / "schedules").exists()
    assert (w.root / "triggers" / "s1.yaml").read_text() == TRIGGER
    assert (w.root / "agents" / "triggers.md").exists()
    assert not (w.root / "agents" / "scheduler.md").exists()
    assert w.repo.is_clean()
    trigger = w.triggers.get("s1")
    assert trigger is not None and trigger.last_fired_at is not None
    assert await w.legacy.list("schedules-state") == []
    text = (w.root / "aios.yaml").read_text()
    assert "triggers:\n  tick_seconds: 10" in text and "# how often" in text
    assert "scheduler" not in text and "schedules" not in text


async def test_running_it_again_changes_nothing(tmp_path) -> None:
    w = RepoWorld(tmp_path)
    _older_repository(w)
    await _migration(w).run()
    head = w.repo.head()

    await _migration(w).run()

    assert w.repo.head() == head


def test_an_older_aios_yaml_is_read_under_the_new_names() -> None:
    import yaml

    config = AppConfig.model_validate(yaml.safe_load(AIOS_YAML))

    assert config.triggers.tick_seconds == 10
    assert config.collection_access == {"triggers": AgentAccess.READ, "roles": AgentAccess.READ}


def test_the_old_collection_name_still_finds_the_triggers(tmp_path) -> None:
    from aios.entities.triggers.trigger import Trigger
    from aios.storage.collection import Collection
    from aios.storage.collection_definition import CollectionDefinition
    from aios.storage.in_memory_document_store import InMemoryDocumentStore

    triggers = Collection(
        CollectionDefinition(
            name="triggers", former_names=frozenset({"schedules"}), entity=Trigger
        ),
        InMemoryDocumentStore(),
    )
    registry = CollectionRegistry([triggers])

    assert registry.get("schedules") is triggers
    assert registry.get("triggers") is triggers
