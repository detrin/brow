import asyncio
import shutil
import subprocess
import sys
import time
from typing import Optional

import typer

from brow import current
from brow.client import BrowAPIError, BrowClient
from brow.config import DAEMON_HOST, DAEMON_PORT, PROFILES_DIR, get_daemon_port, set_daemon_port
from brow.daemon import daemon_running, stop_daemon
from brow.update_check import check_for_update

app = typer.Typer(name="brow", no_args_is_help=True)
daemon_app = typer.Typer(name="daemon", no_args_is_help=True)
session_app = typer.Typer(name="session", no_args_is_help=True)
profile_app = typer.Typer(name="profile", no_args_is_help=True)
state_app = typer.Typer(name="state", no_args_is_help=True)
page_app = typer.Typer(name="page", no_args_is_help=True)

app.add_typer(daemon_app, name="daemon")
app.add_typer(session_app, name="session")
app.add_typer(profile_app, name="profile")
app.add_typer(state_app, name="state")
app.add_typer(page_app, name="page")

session_opt = typer.Option(None, "-s", "--session")


def run_async(fn, *args, **kwargs):
    try:
        return asyncio.run(fn(*args, **kwargs))
    except BrowAPIError as e:
        typer.echo(f"Error ({e.status_code}): {e.detail}", err=True)
        raise typer.Exit(2)


def _client():
    return BrowClient()


async def _explicit(method, path, **kwargs):
    return await getattr(_client(), method)(path, **kwargs)


async def _implicit(method, path, **kwargs):
    client = _client()
    for retry in (False, True):
        sid = await current.resolve(client, refresh=retry)
        try:
            return await getattr(client, method)(path.format(sid=sid), **kwargs)
        except BrowAPIError as e:
            # A cached id outliving its session is normal; re-resolve once instead of failing the command.
            if retry or e.status_code != 404 or "not found" not in (e.detail or ""):
                raise
            current.clear()


async def _resolve(headed):
    return await current.resolve(_client(), headed=headed)


def call(method, path, s=None, **kwargs):
    ensure_daemon()
    if "{sid}" not in path:
        return run_async(_explicit, method, path, **kwargs)
    if s is not None:
        return run_async(_explicit, method, path.format(sid=s), **kwargs)
    return run_async(_implicit, method, path, **kwargs)


def resolved_sid(s, headed=False):
    if s is not None:
        return s
    ensure_daemon()
    return run_async(_resolve, headed)


def _echo_snapshot_hint(result):
    hint = result.get("hint")
    if hint:
        typer.echo(hint, err=True)


def _daemon_healthy(port=None):
    import httpx

    port = get_daemon_port() if port is None else port
    try:
        r = httpx.get(f"http://{DAEMON_HOST}:{port}/status", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def ensure_daemon():
    notice = check_for_update()
    if notice:
        typer.echo(f"[brow] {notice}", err=True)
    if _daemon_healthy():
        return
    subprocess.Popen(
        [sys.executable, "-m", "brow.daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        time.sleep(0.3)
        if _daemon_healthy():
            return
    typer.echo("Failed to start daemon", err=True)
    raise typer.Exit(1)


@app.command("setup")
def setup_cmd(
    with_deps: bool = typer.Option(False, "--with-deps", help="Also install OS-level dependencies"),
    upgrade: bool = typer.Option(
        False, "--upgrade", help="Upgrade patchright first, then install the Chromium build it now expects"
    ),
):
    if upgrade:
        typer.echo("Upgrading patchright...")
        pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "patchright"]
        if subprocess.run(pip_cmd).returncode != 0:
            typer.echo("Failed to upgrade patchright. Try: pip install --upgrade patchright", err=True)
            raise typer.Exit(1)

    cmd = [sys.executable, "-m", "patchright", "install"]
    if with_deps:
        cmd.append("--with-deps")
    cmd.append("chromium")
    typer.echo(
        "Installing the Chromium build patchright now expects..."
        if upgrade
        else "Installing Chromium for brow (~150MB, one-time)..."
    )
    if subprocess.run(cmd).returncode != 0:
        typer.echo("Setup failed. Try: patchright install chromium", err=True)
        raise typer.Exit(1)

    if upgrade and daemon_running():
        # A running daemon holds the old patchright in memory; an on-disk upgrade does nothing until it restarts.
        stop_daemon()
        typer.echo("Stopped the running daemon so it restarts fresh on your next command.")

    typer.echo("Setup complete. Try: brow session new")


@daemon_app.command("start")
def daemon_start(
    port: int = DAEMON_PORT, wait: bool = typer.Option(False, "--wait", help="Block until daemon is ready")
):
    if daemon_running():
        typer.echo("Daemon already running")
        return
    set_daemon_port(port)
    subprocess.Popen(
        [sys.executable, "-m", "brow.daemon", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    if wait:
        for _ in range(50):
            time.sleep(0.3)
            if _daemon_healthy(port):
                typer.echo(f"Daemon ready on {DAEMON_HOST}:{port}")
                return
        typer.echo("Daemon failed to start", err=True)
        raise typer.Exit(1)
    typer.echo(f"Daemon starting on {DAEMON_HOST}:{port}")


@daemon_app.command("stop")
def daemon_stop_cmd():
    if stop_daemon():
        typer.echo("Daemon stopped")
    else:
        typer.echo("Daemon not running")


@daemon_app.command("status")
def daemon_status():
    if not daemon_running():
        typer.echo("Daemon not running")
        return
    result = call("get", "/status")
    typer.echo(f"Running — {result['sessions']} active sessions")


@session_app.command("new")
def session_new(
    profile: Optional[str] = None,
    headed: bool = False,
    url: Optional[str] = None,
    reclaim: bool = typer.Option(False, "--reclaim", help="Close any existing session holding this profile"),
):
    profile = profile or current.default_profile()
    payload = {"profile": profile, "headless": not headed, "reclaim": reclaim}
    if url:
        payload["url"] = url
    result = call("post", "/sessions", json=payload)
    if profile == current.default_profile():
        current.write(result["id"])
    typer.echo(result["id"])
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
    _echo_snapshot_hint(result)


@session_app.command("list")
def session_list():
    sessions = call("get", "/sessions")
    if not sessions:
        typer.echo("No active sessions")
        return
    for s in sessions:
        typer.echo(f"{s['id']}\t{s['profile']}\t{'headed' if not s['headless'] else 'headless'}\t{s['pages']} pages")


@session_app.command("delete")
def session_delete(sid: str):
    call("delete", f"/sessions/{sid}")
    typer.echo(f"Deleted session {sid}")


@session_app.command("cleanup")
def session_cleanup():
    sessions = call("get", "/sessions")
    if not sessions:
        typer.echo("No sessions to clean up")
        return
    for s in sessions:
        call("delete", f"/sessions/{s['id']}")
    typer.echo(f"Cleaned up {len(sessions)} session(s)")


@app.command("login")
def login(url: Optional[str] = typer.Argument(None), profile: Optional[str] = None):
    """Open your profile in a visible window so you can sign in by hand."""
    profile = profile or current.default_profile()
    payload = {"profile": profile, "headless": False, "reclaim": True}
    if url:
        payload["url"] = url
    result = call("post", "/sessions", json=payload)
    sid = result["id"]
    if profile == current.default_profile():
        current.write(sid)
    typer.echo(f"Session {sid} open in a visible window on profile '{profile}'.")
    typer.echo("Sign in, then leave it running — later commands reuse it. Close with:", err=True)
    typer.echo(f"  brow session delete {sid}", err=True)


@app.command("navigate")
def navigate(
    url: str,
    s: Optional[str] = session_opt,
    timeout: int = 30000,
    wait: str = typer.Option("load", "--wait", help="Settle strategy: domcontentloaded | load | networkidle"),
):
    result = call("post", "/browser/{sid}/navigate", s, json={"url": url, "timeout": timeout, "wait": wait})
    typer.echo(f"{result['url']} [{result.get('status', '')}]")
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
    _echo_snapshot_hint(result)


@app.command("wait")
def wait_cmd(selector: Optional[str] = None, load: bool = False, s: Optional[str] = session_opt, timeout: int = 30000):
    call("post", "/browser/{sid}/wait", s, json={"selector": selector, "load": load, "timeout": timeout})
    typer.echo("Done")


@app.command("snapshot")
def snapshot_cmd(
    search: Optional[str] = None,
    locator: Optional[str] = typer.Option(None, "--locator", help="Snapshot only this element's subtree"),
    compact: bool = typer.Option(False, "--compact", help="Show only interactive elements"),
    limit: int = typer.Option(10, "--limit", help="Max lines to keep when --search is used"),
    s: Optional[str] = session_opt,
):
    params = {"limit": limit}
    if search:
        params["search"] = search
    if locator:
        params["locator"] = locator
    if compact:
        params["compact"] = "true"
    result = call("get", "/browser/{sid}/snapshot", s, params=params)
    typer.echo(result["tree"])
    _echo_snapshot_hint(result)


@app.command("screenshot")
def screenshot_cmd(
    full: bool = False,
    path: Optional[str] = None,
    width: Optional[int] = None,
    scale: Optional[float] = None,
    quality: Optional[str] = typer.Option(None, help="low (400px), medium (800px), high (1200px)"),
    s: Optional[str] = session_opt,
):
    payload = {"full": full, "path": path, "width": width, "scale": scale, "quality": quality}
    result = call("post", "/browser/{sid}/screenshot", s, json=payload)
    typer.echo(result["path"])


@app.command("html")
def html_cmd(locator: Optional[str] = None, search: Optional[str] = None, s: Optional[str] = session_opt):
    params = {}
    if locator:
        params["locator"] = locator
    if search:
        params["search"] = search
    result = call("get", "/browser/{sid}/html", s, params=params)
    typer.echo(result["html"])


@app.command("url")
def url_cmd(s: Optional[str] = session_opt):
    result = call("get", "/browser/{sid}/url", s)
    typer.echo(result["url"])


@app.command("logs")
def logs_cmd(search: Optional[str] = None, count: int = 50, s: Optional[str] = session_opt):
    params = {"count": count}
    if search:
        params["search"] = search
    result = call("get", "/browser/{sid}/logs", s, params=params)
    typer.echo(result["logs"])


@app.command("network")
def network_cmd(
    search: Optional[str] = None,
    count: int = 50,
    include_static: bool = typer.Option(False, "--include-static", help="Include images, fonts, scripts, CSS"),
    include_response: bool = typer.Option(False, "--response", help="Include response body preview"),
    clear: bool = typer.Option(False, "--clear", help="Clear the network log"),
    s: Optional[str] = session_opt,
):
    if clear:
        call("delete", "/browser/{sid}/network", s)
        typer.echo("Network log cleared")
        return
    params = {"count": count, "include_static": include_static, "include_response": include_response}
    if search:
        params["search"] = search
    result = call("get", "/browser/{sid}/network", s, params=params)
    typer.echo(result["network"])


@app.command("fetch")
def fetch_cmd(
    url: str,
    method: str = typer.Option("GET", "--method", "-X"),
    header: Optional[list[str]] = typer.Option(None, "--header", "-H", help="Header in 'Key: Value' format"),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="Request body"),
    no_cookies: bool = typer.Option(False, "--no-cookies", help="Plain HTTP request without browser session cookies"),
    s: Optional[str] = session_opt,
):
    headers = {}
    for h in header or []:
        k, _, v = h.partition(":")
        headers[k.strip()] = v.strip()
    payload = {"url": url, "method": method, "headers": headers, "body": data, "no_cookies": no_cookies}
    result = call("post", "/browser/{sid}/fetch", s, json=payload)
    body = result.get("body", "")
    typer.echo(body)
    # An empty-bodied 401 printed nothing, which reads as a successful empty response. stderr keeps pipes clean.
    status = result.get("status")
    if status is not None and not (200 <= int(status) < 300):
        hint = ""
        if int(status) in (401, 403):
            hint = (
                "  (auth failed: the app may require custom headers, or the request "
                "must originate from the app's own origin — navigate there first)"
            )
        typer.echo(f"[brow] HTTP {status}{' — empty body' if not body.strip() else ''}{hint}", err=True)


@app.command("actions")
def actions_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear the action log"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    s: Optional[str] = session_opt,
):
    if clear:
        call("delete", "/browser/{sid}/actions", s)
        typer.echo("Action log cleared")
        return
    result = call("get", "/browser/{sid}/actions", s, params={"as_json": as_json})
    if as_json:
        import json

        typer.echo(json.dumps(result["actions"], indent=2))
    else:
        typer.echo(result["actions"])


@app.command("replay")
def replay_cmd(
    playbook: str = typer.Argument(..., help="Path to playbook YAML file"),
    var: Optional[list[str]] = typer.Option(None, "--var", help="Override variable: key=value"),
    s: Optional[str] = session_opt,
):
    import json

    try:
        import yaml

        with open(playbook) as f:
            pb = yaml.safe_load(f)
    except ImportError:
        import json as _json

        with open(playbook) as f:
            pb = _json.load(f)
    vars_override = {}
    for v in var or []:
        k, _, val = v.partition("=")
        vars_override[k.strip()] = val.strip()
    result = call("post", "/browser/{sid}/replay", s, json={"playbook": pb, "vars": vars_override})
    for r in result["results"]:
        ok = "✓" if r["ok"] else "✗"
        act = r["action"]
        url = r.get("url", "")
        status = r.get("status", "")
        err = r.get("error", "")
        typer.echo(f"{ok}  {act:<10} {url}  {status}  {err}")
        if r.get("data"):
            typer.echo(f"   → {json.dumps(r['data'])[:200]}")
    if any(not r["ok"] for r in result["results"]):
        raise typer.Exit(1)


@app.command("websocket")
def websocket_cmd(
    search: Optional[str] = None,
    count: int = 50,
    clear: bool = typer.Option(False, "--clear", help="Clear the websocket log"),
    s: Optional[str] = session_opt,
):
    if clear:
        call("delete", "/browser/{sid}/websocket", s)
        typer.echo("WebSocket log cleared")
        return
    params = {"count": count}
    if search:
        params["search"] = search
    result = call("get", "/browser/{sid}/websocket", s, params=params)
    typer.echo(result["websocket"])


@app.command("click")
def click_cmd(
    selector: Optional[str] = typer.Argument(None),
    s: Optional[str] = session_opt,
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    timeout: int = 30000,
    retry: int = 0,
    no_wait: bool = typer.Option(False, help="Skip waiting for selector to be visible"),
):
    payload = {"timeout": timeout, "retry": retry, "wait_for_selector": not no_wait}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = call("post", "/browser/{sid}/click", s, json=payload)
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
    _echo_snapshot_hint(result)


@app.command("click-until")
def click_until_cmd(
    selector: str = typer.Argument(..., help="Selector to click each iteration"),
    s: Optional[str] = session_opt,
    until_gone: Optional[str] = typer.Option(None, "--until-gone", help="Stop once this selector has no matches left"),
    max_iterations: int = typer.Option(25, "--max-iterations", help="Safety cap on clicks"),
    settle_ms: int = typer.Option(500, "--settle-ms", help="Wait after each click for the page to refill"),
    timeout: int = typer.Option(30000, "--timeout", help="Per-click timeout in ms"),
):
    """Click a selector repeatedly until the work runs out (paginated/batched UI)."""
    result = call(
        "post",
        f"/browser/{s}/click-until",
        json={
            "selector": selector,
            "until_gone": until_gone,
            "max_iterations": max_iterations,
            "settle_ms": settle_ms,
            "timeout": timeout,
        },
    )
    iterations = result.get("iterations", 0)
    typer.echo(f"Clicked {iterations} time(s)")
    if not result.get("done"):
        # A capped sweep looks identical to a finished one unless the reason is surfaced.
        typer.echo(f"[brow] not done: {result.get('reason')}", err=True)


@app.command("fill")
def fill_cmd(
    args: Optional[list[str]] = typer.Argument(None, help="[SELECTOR] VALUE — selector is optional when --ref is used"),
    s: Optional[str] = session_opt,
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    timeout: int = 30000,
    retry: int = 0,
    no_wait: bool = typer.Option(False, help="Skip waiting for selector to be visible"),
):
    if not args:
        typer.echo("Usage: brow fill [SELECTOR] VALUE [--ref N]", err=True)
        raise typer.Exit(1)
    if len(args) == 1:
        selector, value = None, args[0]
    else:
        selector, value = args[-2], args[-1]
    payload = {"value": value, "timeout": timeout, "retry": retry, "wait_for_selector": not no_wait}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = call("post", "/browser/{sid}/fill", s, json=payload)
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
    _echo_snapshot_hint(result)


@app.command("select")
def select_cmd(
    args: Optional[list[str]] = typer.Argument(None, help="[SELECTOR] VALUE — selector is optional when --ref is used"),
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    s: Optional[str] = session_opt,
    timeout: int = 30000,
):
    if not args:
        typer.echo("Usage: brow select [SELECTOR] VALUE [--ref N]", err=True)
        raise typer.Exit(1)
    if len(args) == 1:
        selector, value = None, args[0]
    else:
        selector, value = args[-2], args[-1]
    payload = {"value": value, "timeout": timeout}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = call("post", "/browser/{sid}/select", s, json=payload)
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
    _echo_snapshot_hint(result)


@app.command("type")
def type_cmd(text: str, s: Optional[str] = session_opt):
    call("post", "/browser/{sid}/type", s, json={"text": text})


@app.command("key")
def key_cmd(key: str, s: Optional[str] = session_opt):
    call("post", "/browser/{sid}/key", s, json={"key": key})


@app.command("hover")
def hover_cmd(selector: str, s: Optional[str] = session_opt, timeout: int = 30000):
    call("post", "/browser/{sid}/hover", s, json={"selector": selector, "timeout": timeout})


@app.command("scroll")
def scroll_cmd(
    pixels: int = 0,
    until: Optional[str] = typer.Option(None, "--until", help="Scroll until selector is visible"),
    max_attempts: int = typer.Option(10, "--max-attempts"),
    s: Optional[str] = session_opt,
):
    if until:
        result = call(
            "post",
            f"/browser/{s}/scroll-until",
            json={"until": until, "pixels": pixels or 800, "max_attempts": max_attempts},
        )
        if result.get("found"):
            typer.echo(f"Found after {result['attempts']} scroll(s)")
        else:
            typer.echo(f"Not found after {result['attempts']} scroll(s)", err=True)
    else:
        call("post", "/browser/{sid}/scroll", s, json={"pixels": pixels})


@app.command("scroll-to")
def scroll_to_cmd(selector: str, s: Optional[str] = session_opt):
    call("post", "/browser/{sid}/scroll", s, json={"selector": selector})


@app.command("drag")
def drag_cmd(source: str, target: str, s: Optional[str] = session_opt):
    call("post", "/browser/{sid}/drag", s, json={"source": source, "target": target})


@app.command("upload")
def upload_cmd(selector: str, filepath: str, s: Optional[str] = session_opt):
    call("post", "/browser/{sid}/upload", s, json={"selector": selector, "filepath": filepath})


@page_app.command("list")
def page_list(s: Optional[str] = session_opt):
    result = call("get", "/pages/{sid}", s)
    for p in result["pages"]:
        typer.echo(f"{p['index']}\t{'*' if p.get('active') else ' '}\t{p['url']}")


@page_app.command("new")
def page_new(
    url: Optional[str] = typer.Argument(None, help="URL to open in the new tab"),
    s: Optional[str] = session_opt,
):
    result = call("post", "/pages/{sid}/new", s, json={"url": url})
    typer.echo(f"Page {result['index']}: {result['url']}")


@page_app.command("close")
def page_close(index: Optional[int] = None, s: Optional[str] = session_opt):
    call("post", "/pages/{sid}/close", s, params={"index": index} if index is not None else {})


@page_app.command("switch")
def page_switch(index: int, s: Optional[str] = session_opt):
    result = call("post", "/pages/{sid}/switch", s, json={"index": index})
    typer.echo(f"Switched to page {result['active']}: {result['url']}")


@profile_app.command("list")
def profile_list():
    result = call("get", "/profiles")
    for p in result["profiles"]:
        typer.echo(p)


@profile_app.command("delete")
def profile_delete(name: str):
    call("delete", f"/profiles/{name}")
    typer.echo(f"Deleted profile {name}")


def _dir_size(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _fmt_size(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


@profile_app.command("prune")
def profile_prune(
    days: int = typer.Option(30, "--days", help="Only consider profiles untouched for this many days"),
    yes: bool = typer.Option(False, "--yes", help="Actually delete; without this it only reports"),
):
    """Delete stale profile directories. Reports only unless --yes is given."""
    if not PROFILES_DIR.exists():
        typer.echo("No profiles directory")
        return

    protected = {current.default_profile(), current.FALLBACK_PROFILE, "default"}
    live = {s["profile"] for s in call("get", "/sessions")}
    cutoff = time.time() - days * 86400

    stale = sorted(
        (p for p in PROFILES_DIR.iterdir() if p.is_dir() and p.name not in protected and p.name not in live),
        key=lambda p: p.stat().st_mtime,
    )
    stale = [p for p in stale if p.stat().st_mtime < cutoff]
    if not stale:
        typer.echo(f"Nothing to prune (no profiles older than {days} days outside {sorted(protected)})")
        return

    total = 0
    for p in stale:
        size = _dir_size(p)
        total += size
        age = int((time.time() - p.stat().st_mtime) / 86400)
        typer.echo(f"{_fmt_size(size):>8}  {age:>4}d  {p.name}")

    if not yes:
        typer.echo(f"\n{len(stale)} profile(s), {_fmt_size(total)} — re-run with --yes to delete", err=True)
        return

    for p in stale:
        shutil.rmtree(p, ignore_errors=True)
    typer.echo(f"\nDeleted {len(stale)} profile(s), freed {_fmt_size(total)}")


@state_app.command("save")
def state_save(name: str, s: Optional[str] = session_opt):
    call("post", "/states/save", json={"name": name, "session_id": resolved_sid(s)})
    typer.echo(f"State saved: {name}")


@state_app.command("restore")
def state_restore(name: str, s: Optional[str] = session_opt):
    call("post", "/states/restore", json={"name": name, "session_id": resolved_sid(s)})
    typer.echo(f"State restored: {name}")


@state_app.command("list")
def state_list():
    result = call("get", "/states")
    for st in result["states"]:
        typer.echo(st)


@app.command("eval")
def eval_cmd(
    code: str,
    s: Optional[str] = session_opt,
    timeout: int = typer.Option(
        30000, "--timeout", help="Max run time in ms. Raise it for long jobs instead of batching them."
    ),
):
    import json

    result = call("post", "/eval/{sid}", s, json={"code": code, "timeout": timeout})
    if result.get("stdout"):
        typer.echo(result["stdout"], nl=False)
    if result.get("result") is not None:
        val = result["result"]
        if isinstance(val, (dict, list)):
            typer.echo(json.dumps(val, indent=2, ensure_ascii=False))
        else:
            typer.echo(str(val))


@app.command("run")
def run_cmd(
    file: str = typer.Argument(..., help="Path to a Python file to run against the session in one call"),
    s: Optional[str] = session_opt,
    timeout: int = typer.Option(
        30000, "--timeout", help="Max run time in ms. Raise it for long jobs instead of batching them."
    ),
    arg: Optional[list[str]] = typer.Option(None, "--arg", help="key=value, available as args['key'] in the script"),
):
    """Run a Python file once inside the session — vars: page, context, browser, state, pages, args."""
    import json

    with open(file) as f:
        code = f.read()

    args = {}
    for a in arg or []:
        k, _, v = a.partition("=")
        args[k.strip()] = v.strip()
    code = f"args = {json.dumps(args)}\n" + code

    result = call("post", "/eval/{sid}", s, json={"code": code, "timeout": timeout})
    if result.get("stdout"):
        typer.echo(result["stdout"], nl=False)
    if result.get("result") is not None:
        val = result["result"]
        if isinstance(val, (dict, list)):
            typer.echo(json.dumps(val, indent=2, ensure_ascii=False))
        else:
            typer.echo(str(val))


if __name__ == "__main__":
    app()
