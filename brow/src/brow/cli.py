import asyncio
import subprocess
import sys
import time
from typing import Optional

import typer

from brow.client import BrowClient
from brow.config import DAEMON_HOST, DAEMON_PORT
from brow.daemon import daemon_running, stop_daemon

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

def run_async(coro):
    return asyncio.run(coro)

def _client():
    return BrowClient()

def _daemon_healthy():
    import httpx
    try:
        r = httpx.get(f"http://{DAEMON_HOST}:{DAEMON_PORT}/status", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False

def ensure_daemon():
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

@daemon_app.command("start")
def daemon_start(port: int = DAEMON_PORT):
    if daemon_running():
        typer.echo("Daemon already running")
        return
    subprocess.Popen(
        [sys.executable, "-m", "brow.daemon", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
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
    c = _client()
    result = run_async(c.get("/status"))
    typer.echo(f"Running — {result['sessions']} active sessions")

@session_app.command("new")
def session_new(profile: str = "default", headed: bool = False, url: Optional[str] = None):
    ensure_daemon()
    c = _client()
    payload = {"profile": profile, "headless": not headed}
    if url:
        payload["url"] = url
    result = run_async(c.post("/sessions", json=payload))
    typer.echo(result["id"])
    if result.get("snapshot"):
        typer.echo(result["snapshot"])

@session_app.command("list")
def session_list():
    ensure_daemon()
    c = _client()
    sessions = run_async(c.get("/sessions"))
    if not sessions:
        typer.echo("No active sessions")
        return
    for s in sessions:
        typer.echo(f"{s['id']}\t{s['profile']}\t{'headed' if not s['headless'] else 'headless'}\t{s['pages']} pages")

@session_app.command("delete")
def session_delete(sid: str):
    ensure_daemon()
    c = _client()
    run_async(c.delete(f"/sessions/{sid}"))
    typer.echo(f"Deleted session {sid}")

@app.command("navigate")
def navigate(url: str, s: Optional[str] = session_opt, timeout: int = 30000):
    ensure_daemon()
    c = _client()
    result = run_async(c.post(f"/browser/{s}/navigate", json={"url": url, "timeout": timeout}))
    typer.echo(f"{result['url']} [{result.get('status', '')}]")

@app.command("wait")
def wait_cmd(selector: Optional[str] = None, load: bool = False, s: Optional[str] = session_opt, timeout: int = 30000):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/wait", json={"selector": selector, "load": load, "timeout": timeout}))
    typer.echo("Done")

@app.command("snapshot")
def snapshot_cmd(search: Optional[str] = None, locator: Optional[str] = None, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    params = {}
    if search:
        params["search"] = search
    if locator:
        params["locator"] = locator
    result = run_async(c.get(f"/browser/{s}/snapshot", params=params))
    typer.echo(result["tree"])

@app.command("screenshot")
def screenshot_cmd(
    full: bool = False,
    path: Optional[str] = None,
    width: Optional[int] = None,
    scale: Optional[float] = None,
    quality: Optional[str] = typer.Option(None, help="low (400px), medium (800px), high (1200px)"),
    s: Optional[str] = session_opt
):
    ensure_daemon()
    c = _client()
    payload = {"full": full, "path": path, "width": width, "scale": scale, "quality": quality}
    result = run_async(c.post(f"/browser/{s}/screenshot", json=payload))
    typer.echo(result["path"])

@app.command("html")
def html_cmd(locator: Optional[str] = None, search: Optional[str] = None, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    params = {}
    if locator:
        params["locator"] = locator
    if search:
        params["search"] = search
    result = run_async(c.get(f"/browser/{s}/html", params=params))
    typer.echo(result["html"])

@app.command("url")
def url_cmd(s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    result = run_async(c.get(f"/browser/{s}/url"))
    typer.echo(result["url"])

@app.command("logs")
def logs_cmd(search: Optional[str] = None, count: int = 50, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    params = {"count": count}
    if search:
        params["search"] = search
    result = run_async(c.get(f"/browser/{s}/logs", params=params))
    typer.echo(result["logs"])

@app.command("click")
def click_cmd(
    selector: Optional[str] = typer.Argument(None),
    s: Optional[str] = session_opt,
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    timeout: int = 30000,
    retry: int = 0,
    no_wait: bool = typer.Option(False, help="Skip waiting for selector to be visible")
):
    ensure_daemon()
    c = _client()
    payload = {"timeout": timeout, "retry": retry, "wait_for_selector": not no_wait}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = run_async(c.post(f"/browser/{s}/click", json=payload))
    if result.get("snapshot"):
        typer.echo(result["snapshot"])

@app.command("fill")
def fill_cmd(
    selector: Optional[str] = typer.Argument(None),
    value: str = typer.Argument(...),
    s: Optional[str] = session_opt,
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    timeout: int = 30000,
    retry: int = 0,
    no_wait: bool = typer.Option(False, help="Skip waiting for selector to be visible")
):
    ensure_daemon()
    c = _client()
    payload = {"value": value, "timeout": timeout, "retry": retry, "wait_for_selector": not no_wait}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = run_async(c.post(f"/browser/{s}/fill", json=payload))
    if result.get("snapshot"):
        typer.echo(result["snapshot"])

@app.command("select")
def select_cmd(
    selector: Optional[str] = typer.Argument(None),
    value: str = typer.Argument(...),
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    s: Optional[str] = session_opt,
    timeout: int = 30000,
):
    ensure_daemon()
    c = _client()
    payload = {"value": value, "timeout": timeout}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    run_async(c.post(f"/browser/{s}/select", json=payload))

@app.command("type")
def type_cmd(text: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/type", json={"text": text}))

@app.command("key")
def key_cmd(key: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/key", json={"key": key}))

@app.command("hover")
def hover_cmd(selector: str, s: Optional[str] = session_opt, timeout: int = 30000):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/hover", json={"selector": selector, "timeout": timeout}))

@app.command("scroll")
def scroll_cmd(pixels: int = 0, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/scroll", json={"pixels": pixels}))

@app.command("scroll-to")
def scroll_to_cmd(selector: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/scroll", json={"selector": selector}))

@app.command("drag")
def drag_cmd(source: str, target: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/drag", json={"source": source, "target": target}))

@app.command("upload")
def upload_cmd(selector: str, filepath: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/upload", json={"selector": selector, "filepath": filepath}))

@page_app.command("list")
def page_list(s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    result = run_async(c.get(f"/pages/{s}"))
    for p in result["pages"]:
        typer.echo(f"{p['index']}\t{p['url']}")

@page_app.command("new")
def page_new(url: Optional[str] = None, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    result = run_async(c.post(f"/pages/{s}/new", json={"url": url}))
    typer.echo(f"Page {result['index']}: {result['url']}")

@page_app.command("close")
def page_close(index: Optional[int] = None, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/pages/{s}/close", params={"index": index} if index is not None else {}))

@page_app.command("switch")
def page_switch(index: int, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    result = run_async(c.post(f"/pages/{s}/switch", json={"index": index}))
    typer.echo(f"Switched to page {result['active']}: {result['url']}")

@profile_app.command("list")
def profile_list():
    ensure_daemon()
    c = _client()
    result = run_async(c.get("/profiles"))
    for p in result["profiles"]:
        typer.echo(p)

@profile_app.command("delete")
def profile_delete(name: str):
    ensure_daemon()
    c = _client()
    run_async(c.delete(f"/profiles/{name}"))
    typer.echo(f"Deleted profile {name}")

@state_app.command("save")
def state_save(name: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post("/states/save", json={"name": name, "session_id": s}))
    typer.echo(f"State saved: {name}")

@state_app.command("restore")
def state_restore(name: str, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    run_async(c.post("/states/restore", json={"name": name, "session_id": s}))
    typer.echo(f"State restored: {name}")

@state_app.command("list")
def state_list():
    ensure_daemon()
    c = _client()
    result = run_async(c.get("/states"))
    for st in result["states"]:
        typer.echo(st)

@app.command("eval")
def eval_cmd(code: str, s: Optional[str] = session_opt, timeout: int = 30000):
    ensure_daemon()
    c = _client()
    result = run_async(c.post(f"/eval/{s}", json={"code": code, "timeout": timeout}))
    if result.get("stdout"):
        typer.echo(result["stdout"], nl=False)
    if result.get("result") is not None:
        typer.echo(result["result"])

if __name__ == "__main__":
    app()
