import platform
import time

SOFTWARE_RENDERERS = ("swiftshader", "llvmpipe", "softpipe", "mesa offscreen")


def _host_timezone():
    return time.strftime("%Z")


def _host_platform():
    return {"Darwin": "MacIntel", "Linux": "Linux x86_64", "Windows": "Win32"}.get(platform.system())


CHECKS = [
    (
        "navigator.webdriver absent",
        lambda p: p["webdriver"] is False,
        "The single most-checked flag. True means every detector sees a bot on the first line of script it runs.",
    ),
    (
        "no automation globals",
        lambda p: not p["automationKeys"] and not p["documentAutomationKeys"],
        "cdc_/__playwright globals on window or document are a direct fingerprint of the driver.",
    ),
    (
        "window.chrome present",
        lambda p: p["hasChromeObject"] is True,
        "Real Chrome always has it; its absence in a Chrome user-agent is a contradiction.",
    ),
    (
        "chrome.runtime present",
        lambda p: p["hasChromeRuntime"] is True,
        "Missing runtime with window.chrome present is the classic patched-but-incomplete signature.",
    ),
    (
        "plugins non-empty",
        lambda p: p["plugins"] > 0,
        "Zero plugins is a headless default and a very cheap check for a detector.",
    ),
    (
        "PDF viewer enabled",
        lambda p: p["pdfViewerEnabled"] is True,
        "Headless Chrome ships without it; desktop Chrome always has it.",
    ),
    (
        "no 'Headless' in UA",
        lambda p: p["headlessInUserAgent"] is False,
        "Self-identifying. Nothing else matters if this is true.",
    ),
    (
        "client hints free of 'Headless'",
        lambda p: not any("headless" in b.lower() for b in ((p["userAgentData"] or {}).get("brands") or [])),
        "navigator.userAgentData is a separate surface from the UA string; sanitising one and not the other is worse than neither.",
    ),
    (
        "window not larger than screen",
        lambda p: p["window"]["outerWidth"] <= p["screen"]["width"] and p["window"]["outerHeight"] <= p["screen"]["height"],
        "A window bigger than the display it is on is physically impossible and costs a detector one comparison.",
    ),
    (
        "hardware-accelerated WebGL",
        lambda p: bool(p["webgl"]) and not any(s in (p["webgl"]["renderer"] or "").lower() for s in SOFTWARE_RENDERERS),
        "SwiftShader/llvmpipe means no GPU, which on consumer hardware means a datacentre or a headless run.",
    ),
    (
        "notification permission not denied",
        lambda p: p["notificationPermission"] != "denied",
        "'denied' without the user ever being asked is a headless default.",
    ),
    (
        "permissions API self-consistent",
        lambda p: not (p["notificationPermission"] == "denied" and p["permissionQueryState"] == "prompt"),
        "Notification.permission and permissions.query() disagreeing is the classic headless contradiction.",
    ),
    (
        "native function toString",
        lambda p: p["nativeToString"] is True,
        "A patched built-in that no longer reports [native code] is worse than the flag it was hiding.",
    ),
    (
        "stack traces clean",
        lambda p: p["stackMentionsDriver"] is False,
        "Driver names leaking into Error().stack identify the tool exactly.",
    ),
    (
        "plausible core count",
        lambda p: isinstance(p["hardwareConcurrency"], int) and p["hardwareConcurrency"] >= 2,
        "A 1-core machine browsing the web in 2026 is a container.",
    ),
    (
        "timezone matches host",
        lambda p: bool(p["timezone"]),
        "A UTC browser on a non-UTC machine is a mismatch detectors correlate against IP geolocation.",
    ),
    (
        "platform matches host OS",
        lambda p: _host_platform() is None or p["platform"] == _host_platform(),
        "navigator.platform disagreeing with the real OS is an incoherent fingerprint.",
    ),
]


REQUIRED_KEYS = ("userAgent", "webdriver", "platform", "hardwareConcurrency")


def unusable(probe):
    if not isinstance(probe, dict):
        return f"probe returned {type(probe).__name__} {str(probe)[:160]!r}, not an object"
    missing = [k for k in REQUIRED_KEYS if probe.get(k) is None]
    if missing:
        return f"probe returned no value for {', '.join(missing)}"
    return None


def score(probe):
    checks = {}
    for name, test, why in CHECKS:
        try:
            ok = bool(test(probe))
        except Exception as e:
            ok = False
            why = f"{why} (check errored: {e})"
        checks[name] = {"pass": ok, "why": why}
    return {
        "passed": sum(1 for c in checks.values() if c["pass"]),
        "total": len(CHECKS),
        "checks": checks,
    }


def host_context():
    return {"platform": _host_platform(), "timezone": _host_timezone(), "system": platform.system()}
