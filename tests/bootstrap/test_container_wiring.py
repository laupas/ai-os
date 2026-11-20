from aios.bootstrap.application import Application
from aios.bootstrap.application_container import ApplicationContainer
from aios.tools.aios_tool_server import AiosToolServer


def test_every_provider_resolves(tmp_path, monkeypatch) -> None:
    (tmp_path / "config.yaml").write_text(
        "channels: [web]\nsenders: [signal, mail]\nowner: {name: Alice}\n"
    )
    monkeypatch.setenv("AIOS_DATA_DIR", str(tmp_path))
    container = ApplicationContainer()

    assert isinstance(container.application(), Application)
    assert isinstance(container.tools.server(), AiosToolServer)
    assert container.channels.senders().names() == ["signal", "mail"]
    assert [c.name for c in container.channels.directory().enabled()] == ["web"]
    assert container.engine.options_factory() is not None


def test_the_console_gets_the_collections_whose_access_can_change(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIOS_DATA_DIR", str(tmp_path))
    container = ApplicationContainer()
    container.storage.registry()  # builds every collection, as the start does
    defaults = container.storage.collection_overrides().defaults()
    assert "memories" in defaults and "agents" not in defaults
