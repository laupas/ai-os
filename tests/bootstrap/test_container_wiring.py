from aios.bootstrap.application import Application
from aios.bootstrap.application_container import ApplicationContainer
from aios.tools.aios_tool_server import AiosToolServer


def test_every_provider_resolves(tmp_path, monkeypatch) -> None:
    (tmp_path / "config.yaml").write_text(
        "channels: [cli]\nsenders: [signal, mail]\nowner: {name: Alice}\n"
    )
    monkeypatch.setenv("AIOS_DATA_DIR", str(tmp_path))
    container = ApplicationContainer()

    assert isinstance(container.application(), Application)
    assert isinstance(container.tools.server(), AiosToolServer)
    assert container.messaging.directory().names() == ["signal", "mail"]
    assert [c.name for c in container.channels.directory().enabled()] == ["cli"]
    assert container.engine.options_factory() is not None
