import json
import os

from brow.config import BROW_HOME

CURRENT_FILE = BROW_HOME / "current.json"
FALLBACK_PROFILE = "personal"


def default_profile():
    return os.environ.get("BROW_PROFILE") or FALLBACK_PROFILE


def read():
    try:
        data = json.loads(CURRENT_FILE.read_text())
    except (OSError, ValueError):
        return None
    return data.get("sid") if data.get("profile") == default_profile() else None


def write(sid):
    CURRENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURRENT_FILE.write_text(json.dumps({"sid": sid, "profile": default_profile()}))


def clear():
    CURRENT_FILE.unlink(missing_ok=True)


async def resolve(client, headed=False, refresh=False):
    if not refresh:
        cached = read()
        if cached:
            return cached
    profile = default_profile()
    for s in await client.get("/sessions"):
        if s["profile"] == profile:
            write(s["id"])
            return s["id"]
    created = await client.post("/sessions", json={"profile": profile, "headless": not headed, "reclaim": True})
    write(created["id"])
    return created["id"]
