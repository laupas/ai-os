import pytest

from aios.channels.channel_capability import ChannelCapability
from aios.channels.channel_catalog import ChannelCatalog
from aios.channels.channel_values import ChannelValues
from aios.config.app_config import AppConfig
from aios.config.channel_config import ChannelConfig
from aios.entities.variables.variable import Variable
from aios.storage.collection import Collection
from aios.storage.collection_definition import CollectionDefinition
from aios.variables.secret_box import SecretBox
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver
from tests.fakes.fake_channel_type import FakeChannelType
from tests.fakes.fake_clock import FakeClock
from tests.fakes.world import World


def values(tmp_path, world: World) -> tuple[ChannelValues, VariableCatalog]:
    variables: Collection[Variable] = Collection(
        CollectionDefinition(name="variables", entity=Variable), world.store
    )
    box = SecretBox("a test key, long enough for one")
    resolver = VariableResolver(variables, box, tmp_path / "files")
    return ChannelValues(resolver), VariableCatalog(variables, box, FakeClock())


def test_the_older_two_lists_are_read_as_one_map() -> None:
    config = AppConfig.model_validate({"channels": ["slack", "web"], "senders": ["signal"]})
    assert config.enabled_channels() == ["slack", "web", "signal"]
    only_senders = AppConfig.model_validate({"senders": ["mail"]})
    assert only_senders.enabled_channels() == ["web", "mail"]
    assert AppConfig().enabled_channels() == ["web"]


def test_a_channel_named_without_anything_is_on_and_one_can_be_off() -> None:
    config = AppConfig.model_validate({"channels": {"slack": None, "mail": {"enabled": False}}})
    assert config.enabled_channels() == ["slack"]


async def test_the_variable_wins_over_the_environment_and_that_over_the_default(
    tmp_path, monkeypatch
) -> None:
    world = World()
    await world.setup()
    channel_values, catalog = values(tmp_path, world)
    fake = FakeChannelType()
    assert channel_values.of(fake) == {"FAKE_TOKEN": None, "FAKE_URL": "http://x"}
    assert channel_values.missing(fake) == ["FAKE_TOKEN"]
    monkeypatch.setenv("FAKE_TOKEN", "from-env")
    assert channel_values.of(fake)["FAKE_TOKEN"] == "from-env"
    await catalog.save("FAKE_TOKEN", "from-console", True, False, "", "alice")
    assert channel_values.of(fake)["FAKE_TOKEN"] == "from-console"
    assert channel_values.of(fake, {"FAKE_TOKEN": "typed"})["FAKE_TOKEN"] == "typed"


async def test_a_chat_channel_needs_its_values_and_a_sender_does_not(tmp_path) -> None:
    world = World()
    await world.setup()
    channel_values, _ = values(tmp_path, world)
    fake = FakeChannelType()
    catalog = ChannelCatalog([fake], {"fake": ChannelConfig()}, channel_values)
    assert catalog.enabled(ChannelCapability.CHAT) == ["fake"]
    with pytest.raises(RuntimeError, match="FAKE_TOKEN"):
        catalog.channel_factories()["fake"]()
    assert catalog.sender_factories()["fake"]().name == "fake"


async def test_an_unknown_or_switched_off_channel(tmp_path) -> None:
    world = World()
    await world.setup()
    channel_values, _ = values(tmp_path, world)
    with pytest.raises(ValueError, match="nope"):
        ChannelCatalog([FakeChannelType()], {"nope": ChannelConfig()}, channel_values)
    off = ChannelCatalog(
        [FakeChannelType()], {"fake": ChannelConfig(enabled=False)}, channel_values
    )
    assert off.enabled(ChannelCapability.SEND) == []
