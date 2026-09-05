import platform
import re
import subprocess
from functools import lru_cache

# headless=True alone runs chrome-headless-shell, which has no GPU, no plugins, no PDF viewer
# and no window.chrome. channel="chromium" runs the full build in Chrome's new headless mode
# instead and fixes all of those at once: benchmarks/stealth scores 7/15 without it, 13/15 with.
CHANNEL = "chromium"

ARGS = ["--disable-blink-features=AutomationControlled"]
IGNORE_DEFAULT_ARGS = ["--enable-automation"]

UA_PLATFORM = {
    "Darwin": "Macintosh; Intel Mac OS X 10_15_7",
    "Windows": "Windows NT 10.0; Win64; x64",
    "Linux": "X11; Linux x86_64",
}


@lru_cache(maxsize=8)
def _major_version(executable):
    try:
        out = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.\d+\.\d+\.\d+", out or "")
    return m.group(1) if m else None


def user_agent(executable):
    token = UA_PLATFORM.get(platform.system())
    major = _major_version(executable) if token else None
    if not major:
        return None
    return (
        f"Mozilla/5.0 ({token}) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def launch_kwargs(user_data_dir, headless, executable):
    kwargs = {
        "user_data_dir": str(user_data_dir),
        "headless": headless,
        "args": list(ARGS),
        "ignore_default_args": list(IGNORE_DEFAULT_ARGS),
    }
    if not headless:
        return kwargs
    kwargs["channel"] = CHANNEL
    ua = user_agent(executable)
    if ua:
        kwargs["user_agent"] = ua
    return kwargs
