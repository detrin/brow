import pytest

from brow import config


def test_ensure_dirs(tmp_brow_home):
    config.ensure_dirs()

    assert config.BROW_HOME.exists()


def test_daemon_port_is_persisted_for_later_processes(tmp_path, monkeypatch):
    port_file = tmp_path / "daemon.port"
    monkeypatch.setattr(config, "PORT_FILE", port_file, raising=False)

    config.set_daemon_port(20990)

    assert port_file.read_text() == "20990"
    assert config.get_daemon_port(env={}) == 20990


def test_brow_port_environment_variable_overrides_persisted_port(tmp_path, monkeypatch):
    port_file = tmp_path / "daemon.port"
    port_file.write_text("20990")
    monkeypatch.setattr(config, "PORT_FILE", port_file, raising=False)

    assert config.get_daemon_port(env={"BROW_PORT": "20991"}) == 20991


def test_corrupt_persisted_port_falls_back_to_default(tmp_path, monkeypatch):
    port_file = tmp_path / "daemon.port"
    port_file.write_text("not-a-port")
    monkeypatch.setattr(config, "PORT_FILE", port_file, raising=False)

    assert config.get_daemon_port(env={}) == 19987


@pytest.mark.parametrize("port", [0, 65536])
def test_refuses_to_persist_invalid_daemon_port(port):
    with pytest.raises(ValueError, match="port"):
        config.set_daemon_port(port)
