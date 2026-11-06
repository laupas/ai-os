from aios.agents.agent_catalog import AgentCatalog
from aios.agents.skill_catalog import SkillCatalog
from aios.entities.skills.skill import Skill
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.in_memory_document_store import InMemoryDocumentStore
from aios.tools.config_editor import ConfigEditor
from aios.variables.secret_extractor import SecretExtractor
from tests.agents.agent_world import AgentWorld
from tests.variables.test_variables import _world


async def test_literal_secrets_become_encrypted_variables(tmp_path) -> None:
    catalog, resolver = _world(tmp_path)
    extractor = SecretExtractor(catalog, resolver)
    config = {
        "type": "http",
        "url": "https://mcp.example.com",
        "headers": {"Authorization": "Bearer s3cret", "X-Trace": "on", "X-Api-Key": "${KEY}"},
        "env": {"API_TOKEN": "t0ken", "NODE_OPTIONS": "--require x", "KEY_FILE": "/k.json"},
        "oauth": {"client_id": "cid", "client_secret": "cl1ent"},
    }
    cleaned, moved = await extractor.extract("my-mail", config, "Alice")
    assert moved == ["MY_MAIL_AUTHORIZATION", "MY_MAIL_API_TOKEN", "MY_MAIL_CLIENT_SECRET"]
    assert cleaned["headers"] == {
        "Authorization": "${MY_MAIL_AUTHORIZATION}",
        "X-Trace": "on",  # not a secret by its name
        "X-Api-Key": "${KEY}",  # already a reference
    }
    assert cleaned["env"] == {
        "API_TOKEN": "${MY_MAIL_API_TOKEN}",
        "NODE_OPTIONS": "--require x",
        "KEY_FILE": "/k.json",  # a path
    }
    assert cleaned["oauth"] == {"client_id": "cid", "client_secret": "${MY_MAIL_CLIENT_SECRET}"}
    assert config["headers"]["Authorization"] == "Bearer s3cret"  # the input is not changed
    stored = (tmp_path / "data" / "variables" / "MY_MAIL_AUTHORIZATION.json").read_text()
    assert "s3cret" not in stored
    assert resolver.expand(cleaned)["headers"]["Authorization"] == "Bearer s3cret"
    variable = catalog.get("MY_MAIL_API_TOKEN")
    assert variable is not None and variable.secret and variable.updated_by == "Alice"


async def test_a_name_in_use_for_another_value_is_not_overwritten(tmp_path) -> None:
    catalog, resolver = _world(tmp_path)
    extractor = SecretExtractor(catalog, resolver)
    await catalog.save("X_API_TOKEN", "other", True, False, "", "Alice")
    cleaned, moved = await extractor.extract("x", {"env": {"API_TOKEN": "mine"}}, "Alice")
    assert moved == ["X_API_TOKEN_2"] and resolver.value_of("X_API_TOKEN") == "other"
    again, _ = await extractor.extract("x", {"env": {"API_TOKEN": "mine"}}, "Alice")
    assert again == cleaned  # saving the same value again reuses its variable


async def test_nothing_to_move_leaves_the_config_alone(tmp_path) -> None:
    catalog, resolver = _world(tmp_path)
    config = {"command": "npx", "args": ["-y", "server"], "env": {"TOKEN": "${T}"}}
    cleaned, moved = await SecretExtractor(catalog, resolver).extract("x", config, "Alice")
    assert cleaned == config and moved == [] and catalog.all() == []


async def test_the_configurator_cannot_commit_a_literal_secret(tmp_path) -> None:
    catalog, resolver = _world(tmp_path)
    w = AgentWorld(tmp_path)
    skills: Collection[Skill] = Collection(
        CollectionDefinition(name="skills", entity=Skill), InMemoryDocumentStore()
    )
    editor = ConfigEditor(
        AgentCatalog(w.store),
        SkillCatalog(skills),
        w.connector_store,
        SecretExtractor(catalog, resolver),
    )
    await editor.save(
        "connectors",
        {
            "id": "svc",
            "config": {
                "type": "http",
                "url": "https://s",
                "headers": {"Authorization": "Bearer abc"},
            },
        },
    )
    saved = w.connector_store.get("svc")
    assert saved is not None and saved.config["headers"]["Authorization"] == "${SVC_AUTHORIZATION}"
    assert catalog.get("SVC_AUTHORIZATION") is not None


async def test_a_deleted_variable_takes_its_file_with_it(tmp_path) -> None:
    catalog, resolver = _world(tmp_path)
    await catalog.save("KEYS", "{}", True, True, "", "Alice")
    path = resolver.expand("${file:KEYS}")
    assert (tmp_path / "files" / "KEYS").exists() and path.endswith("KEYS")
    resolver.forget("KEYS")
    assert not any((tmp_path / "files").iterdir())
