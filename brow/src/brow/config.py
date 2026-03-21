from pathlib import Path
import os

BROW_HOME = Path(os.environ.get("BROW_HOME", Path.home() / ".brow"))
PROFILES_DIR = BROW_HOME / "profiles"
STATES_DIR = BROW_HOME / "states"
SCREENSHOTS_DIR = BROW_HOME / "screenshots"
PID_FILE = BROW_HOME / "daemon.pid"
LOG_FILE = BROW_HOME / "daemon.log"

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = int(os.environ.get("BROW_PORT", "19987"))
DAEMON_URL = f"http://{DAEMON_HOST}:{DAEMON_PORT}"

MAX_SESSIONS = int(os.environ.get("BROW_MAX_SESSIONS", "10"))
DEFAULT_TIMEOUT = 30000

def ensure_dirs():
    for d in [BROW_HOME, PROFILES_DIR, STATES_DIR, SCREENSHOTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
