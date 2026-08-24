"""Best-effort "a newer brow-cli is available" notice.

Never blocks a command for long and never raises: any network, filesystem,
or parsing failure just means no notice this run. Cached so most
invocations don't touch the network at all. Disable entirely with
BROW_NO_UPDATE_CHECK=1.
"""

import json
import os
import time
from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from packaging.version import InvalidVersion, Version

from brow.config import UPDATE_CHECK_FILE, ensure_dirs

PACKAGE_NAME = "brow-cli"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
FETCH_TIMEOUT_S = 1.5
CHECK_INTERVAL_S = 24 * 60 * 60
RETRY_INTERVAL_S = 60 * 60  # retry sooner than a full day if the last check failed


def _current_version() -> Optional[str]:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return None


def _parse_version(v: str) -> Optional[Version]:
    try:
        return Version(v)
    except InvalidVersion:
        return None


def _fetch_latest_version() -> Optional[str]:
    try:
        import httpx

        r = httpx.get(PYPI_URL, timeout=FETCH_TIMEOUT_S)
        r.raise_for_status()
        return r.json()["info"]["version"]
    except Exception:
        return None


def _read_cache() -> dict:
    try:
        return json.loads(UPDATE_CHECK_FILE.read_text())
    except Exception:
        return {}


def _write_cache(data: dict) -> None:
    try:
        ensure_dirs()
        UPDATE_CHECK_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def check_for_update(env=None) -> Optional[str]:
    """Return a one-line update notice, or None if none is due."""
    env = env if env is not None else os.environ
    if env.get("BROW_NO_UPDATE_CHECK"):
        return None

    current = _current_version()
    if not current:
        return None

    cache = _read_cache()
    now = time.time()
    latest = cache.get("latest")
    checked_at = cache.get("checked_at", 0)
    interval = CHECK_INTERVAL_S if latest else RETRY_INTERVAL_S

    if now - checked_at > interval:
        fetched = _fetch_latest_version()
        if fetched:
            latest = fetched
            _write_cache({"checked_at": now, "latest": latest})
        else:
            _write_cache({"checked_at": now, "latest": latest})

    if not latest:
        return None

    latest_version = _parse_version(latest)
    current_version = _parse_version(current)
    if latest_version is not None and current_version is not None and latest_version > current_version:
        return f"brow {latest} is available (you have {current}). Update with: pip install --upgrade brow-cli"
    return None
