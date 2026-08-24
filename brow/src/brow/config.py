import os
from pathlib import Path

BROW_HOME = Path(os.environ.get("BROW_HOME", Path.home() / ".brow"))
PROFILES_DIR = BROW_HOME / "profiles"
STATES_DIR = BROW_HOME / "states"
SCREENSHOTS_DIR = BROW_HOME / "screenshots"
PID_FILE = BROW_HOME / "daemon.pid"
LOG_FILE = BROW_HOME / "daemon.log"
UPDATE_CHECK_FILE = BROW_HOME / "update_check.json"
PORT_FILE = BROW_HOME / "daemon.port"

DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 19987


def _validate_daemon_port(value) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid daemon port: {value!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid daemon port: {port}; expected 1-65535")
    return port


def get_daemon_port(env=None) -> int:
    env = os.environ if env is None else env
    if "BROW_PORT" in env:
        return _validate_daemon_port(env["BROW_PORT"])
    try:
        return _validate_daemon_port(PORT_FILE.read_text().strip())
    except (OSError, ValueError):
        return DEFAULT_DAEMON_PORT


def set_daemon_port(port: int) -> None:
    port = _validate_daemon_port(port)
    PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORT_FILE.write_text(str(port))


def get_daemon_url(port=None) -> str:
    return f"http://{DAEMON_HOST}:{get_daemon_port() if port is None else _validate_daemon_port(port)}"


DAEMON_PORT = get_daemon_port()
DAEMON_URL = get_daemon_url(DAEMON_PORT)

MAX_SESSIONS = int(os.environ.get("BROW_MAX_SESSIONS", "10"))
DEFAULT_TIMEOUT = 30000


def ensure_dirs():
    for d in [BROW_HOME, PROFILES_DIR, STATES_DIR, SCREENSHOTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
