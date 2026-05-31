import sys

import pytest


@pytest.fixture(autouse=True)
def tmp_brow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BROW_HOME", str(tmp_path / ".brow"))
    if "brow.config" in sys.modules:
        del sys.modules["brow.config"]
    if "brow.profiles" in sys.modules:
        del sys.modules["brow.profiles"]
    import brow.config as cfg

    cfg.BROW_HOME = tmp_path / ".brow"
    cfg.PROFILES_DIR = cfg.BROW_HOME / "profiles"
    cfg.STATES_DIR = cfg.BROW_HOME / "states"
    cfg.SCREENSHOTS_DIR = cfg.BROW_HOME / "screenshots"
    cfg.PID_FILE = cfg.BROW_HOME / "daemon.pid"
    cfg.LOG_FILE = cfg.BROW_HOME / "daemon.log"
    cfg.DAEMON_URL = f"http://{cfg.DAEMON_HOST}:{cfg.DAEMON_PORT}"
    cfg.ensure_dirs()
