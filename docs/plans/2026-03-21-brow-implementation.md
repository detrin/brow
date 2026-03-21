# brow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Playwright CLI tool (`brow`) with a FastAPI daemon for agent browser automation.

**Architecture:** Typer CLI sends HTTP requests to a FastAPI daemon running on localhost:19987. The daemon manages Playwright browser sessions with persistent Chromium profiles. Sessions are isolated (one browser per session) with sequential integer IDs.

**Tech Stack:** playwright, fastapi, uvicorn, typer, httpx

**Spec:** `docs/specs/2026-03-21-brow-design.md`

---

## File Structure

```
brow/
├── pyproject.toml
├── src/
│   └── brow/
│       ├── __init__.py          # version
│       ├── config.py            # paths, port, defaults
│       ├── session.py           # Session class + SessionManager
│       ├── profiles.py          # ProfileManager
│       ├── snapshot.py          # accessibility tree extraction
│       ├── daemon.py            # FastAPI app + uvicorn launcher
│       ├── client.py            # HTTP client (CLI -> daemon)
│       ├── cli.py               # Typer CLI entry point
│       └── routes/
│           ├── __init__.py
│           ├── sessions.py      # session CRUD
│           ├── browser.py       # navigation, interaction, observation
│           ├── pages.py         # page management
│           ├── profiles.py      # profile/state management
│           └── eval.py          # eval escape hatch
└── tests/
    ├── conftest.py              # shared fixtures
    ├── test_config.py
    ├── test_session.py
    ├── test_profiles.py
    ├── test_snapshot.py
    ├── test_routes_sessions.py
    ├── test_routes_browser.py
    ├── test_routes_pages.py
    ├── test_routes_profiles.py
    ├── test_routes_eval.py
    ├── test_client.py
    └── test_cli.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `brow/pyproject.toml`
- Create: `brow/src/brow/__init__.py`
- Create: `brow/src/brow/config.py`
- Create: `brow/src/brow/routes/__init__.py`
- Create: `brow/tests/conftest.py`
- Create: `brow/.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "brow-cli"
version = "0.1.0"
description = "Standalone Playwright CLI for agent browser automation"
requires-python = ">=3.11"
dependencies = [
    "playwright>=1.40",
    "fastapi>=0.104",
    "uvicorn>=0.24",
    "typer>=0.9",
    "httpx>=0.25",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.28",
    "httpx>=0.25",
]

[project.scripts]
brow = "brow.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/brow"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create __init__.py**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create config.py**

```python
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
```

- [ ] **Step 4: Create routes/__init__.py (empty), conftest.py, .gitignore**

conftest.py:
```python
import pytest
from brow.config import BROW_HOME

@pytest.fixture(autouse=True)
def tmp_brow_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BROW_HOME", str(tmp_path / ".brow"))
    import brow.config as cfg
    cfg.BROW_HOME = tmp_path / ".brow"
    cfg.PROFILES_DIR = cfg.BROW_HOME / "profiles"
    cfg.STATES_DIR = cfg.BROW_HOME / "states"
    cfg.SCREENSHOTS_DIR = cfg.BROW_HOME / "screenshots"
    cfg.PID_FILE = cfg.BROW_HOME / "daemon.pid"
    cfg.LOG_FILE = cfg.BROW_HOME / "daemon.log"
    cfg.ensure_dirs()
```

- [ ] **Step 5: Create venv + install deps**

```bash
cd brow && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

- [ ] **Step 6: Run pytest to verify setup**

Run: `cd brow && pytest --co -q`
Expected: no errors, 0 tests collected

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: project scaffolding with pyproject.toml and config"
```

---

### Task 2: Session + SessionManager

**Files:**
- Create: `brow/src/brow/session.py`
- Create: `brow/tests/test_session.py`

- [ ] **Step 1: Write test_session.py**

```python
import pytest
from brow.session import SessionManager

@pytest.fixture
def manager():
    return SessionManager()

def test_create_session(manager):
    sid = manager.create("default", headless=True)
    assert sid == "1"
    assert "1" in manager.sessions

def test_sequential_ids(manager):
    s1 = manager.create("a", headless=True)
    s2 = manager.create("b", headless=True)
    assert s1 == "1"
    assert s2 == "2"

def test_delete_session(manager):
    sid = manager.create("default", headless=True)
    manager.delete(sid)
    assert sid not in manager.sessions

def test_delete_nonexistent(manager):
    with pytest.raises(KeyError):
        manager.delete("999")

def test_get_session(manager):
    sid = manager.create("default", headless=True)
    session = manager.get(sid)
    assert session.profile == "default"

def test_max_sessions(manager, monkeypatch):
    monkeypatch.setattr("brow.session.MAX_SESSIONS", 2)
    manager.create("a", headless=True)
    manager.create("b", headless=True)
    with pytest.raises(RuntimeError, match="Max sessions"):
        manager.create("c", headless=True)

def test_list_sessions(manager):
    manager.create("a", headless=True)
    manager.create("b", headless=True)
    result = manager.list()
    assert len(result) == 2

def test_duplicate_profile(manager):
    manager.create("gmail", headless=True)
    with pytest.raises(RuntimeError, match="already in use"):
        manager.create("gmail", headless=True)
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_session.py -v`
Expected: FAIL (no module)

- [ ] **Step 3: Implement session.py**

```python
from dataclasses import dataclass, field
from brow.config import MAX_SESSIONS

@dataclass
class Session:
    id: str
    profile: str
    headless: bool
    browser: object = None
    context: object = None
    state: dict = field(default_factory=dict)

    @property
    def pages(self):
        return self.context.pages if self.context else []

    @property
    def page(self):
        pages = self.pages
        return pages[-1] if pages else None

    async def launch(self, playwright, user_data_dir):
        self.browser = None
        self.context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=self.headless,
        )

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
        self.browser = None

class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self._counter = 0

    def create(self, profile, headless=True):
        if len(self.sessions) >= MAX_SESSIONS:
            raise RuntimeError(f"Max sessions ({MAX_SESSIONS}) reached")
        for s in self.sessions.values():
            if s.profile == profile:
                raise RuntimeError(f"Profile '{profile}' already in use by session {s.id}")
        self._counter += 1
        sid = str(self._counter)
        self.sessions[sid] = Session(id=sid, profile=profile, headless=headless)
        return sid

    def get(self, sid):
        if sid not in self.sessions:
            raise KeyError(f"Session {sid} not found")
        return self.sessions[sid]

    def delete(self, sid):
        if sid not in self.sessions:
            raise KeyError(f"Session {sid} not found")
        del self.sessions[sid]

    def list(self):
        return [{"id": s.id, "profile": s.profile, "headless": s.headless, "pages": len(s.pages)} for s in self.sessions.values()]

    async def close_all(self):
        for s in self.sessions.values():
            await s.close()
        self.sessions.clear()
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_session.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/brow/session.py tests/test_session.py
git commit -m "feat: Session model and SessionManager"
```

---

### Task 3: ProfileManager

**Files:**
- Create: `brow/src/brow/profiles.py`
- Create: `brow/tests/test_profiles.py`

- [ ] **Step 1: Write test_profiles.py**

```python
import json
import pytest
from brow.profiles import ProfileManager

@pytest.fixture
def pm():
    return ProfileManager()

def test_get_or_create_profile(pm):
    path = pm.get_profile_dir("gmail")
    assert path.exists()
    assert path.name == "gmail"

def test_list_profiles(pm):
    pm.get_profile_dir("gmail")
    pm.get_profile_dir("work")
    profiles = pm.list()
    assert set(profiles) == {"gmail", "work"}

def test_delete_profile(pm):
    pm.get_profile_dir("gmail")
    pm.delete("gmail")
    assert "gmail" not in pm.list()

def test_delete_nonexistent(pm):
    with pytest.raises(KeyError):
        pm.delete("nope")

def test_save_state(pm, tmp_brow_home):
    state = {"cookies": [{"name": "a", "value": "b"}], "origins": []}
    pm.save_state("gmail-auth", state)
    loaded = pm.load_state("gmail-auth")
    assert loaded == state

def test_load_nonexistent_state(pm):
    with pytest.raises(FileNotFoundError):
        pm.load_state("nope")

def test_list_states(pm):
    pm.save_state("s1", {"cookies": []})
    pm.save_state("s2", {"cookies": []})
    assert set(pm.list_states()) == {"s1", "s2"}
```

- [ ] **Step 2: Run tests, verify fail**

Run: `pytest tests/test_profiles.py -v`

- [ ] **Step 3: Implement profiles.py**

```python
import json
import shutil
from brow.config import PROFILES_DIR, STATES_DIR, ensure_dirs

class ProfileManager:
    def __init__(self):
        ensure_dirs()

    def get_profile_dir(self, name):
        p = PROFILES_DIR / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def list(self):
        if not PROFILES_DIR.exists():
            return []
        return [d.name for d in PROFILES_DIR.iterdir() if d.is_dir()]

    def delete(self, name):
        p = PROFILES_DIR / name
        if not p.exists():
            raise KeyError(f"Profile '{name}' not found")
        shutil.rmtree(p)

    def save_state(self, name, state):
        ensure_dirs()
        (STATES_DIR / f"{name}.json").write_text(json.dumps(state, indent=2))

    def load_state(self, name):
        path = STATES_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"State '{name}' not found")
        return json.loads(path.read_text())

    def list_states(self):
        if not STATES_DIR.exists():
            return []
        return [p.stem for p in STATES_DIR.glob("*.json")]
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_profiles.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/brow/profiles.py tests/test_profiles.py
git commit -m "feat: ProfileManager with state save/restore"
```

---

### Task 4: Snapshot Module

**Files:**
- Create: `brow/src/brow/snapshot.py`
- Create: `brow/tests/test_snapshot.py`

- [ ] **Step 1: Write test_snapshot.py**

```python
import re
from brow.snapshot import format_tree, filter_lines

SAMPLE_TREE = {
    "role": "WebArea",
    "name": "Example",
    "children": [
        {"role": "heading", "name": "Hello", "level": 1},
        {"role": "link", "name": "Click me"},
        {"role": "textbox", "name": "Email"},
    ]
}

def test_format_tree():
    result = format_tree(SAMPLE_TREE)
    assert "heading" in result
    assert "Hello" in result
    assert "link" in result

def test_format_tree_none():
    assert format_tree(None) == ""

def test_filter_lines():
    text = "line one\nline two\nline three"
    result = filter_lines(text, "two")
    assert "two" in result
    assert "one" not in result

def test_filter_lines_regex():
    text = "apple 1\nbanana 2\napricot 3"
    result = filter_lines(text, "^ap")
    assert "apple" in result
    assert "apricot" in result
    assert "banana" not in result

def test_filter_lines_limit():
    text = "\n".join(f"match {i}" for i in range(20))
    result = filter_lines(text, "match", limit=10)
    lines = [l for l in result.strip().split("\n") if l]
    assert len(lines) == 10
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement snapshot.py**

```python
import re

def format_tree(tree, indent=0):
    if not tree:
        return ""
    lines = []
    prefix = "  " * indent
    role = tree.get("role", "")
    name = tree.get("name", "")
    extras = ""
    if "level" in tree:
        extras += f" level={tree['level']}"
    if "value" in tree:
        extras += f" value=\"{tree['value']}\""
    if "checked" in tree:
        extras += f" checked={tree['checked']}"
    line = f"{prefix}{role}"
    if name:
        line += f" \"{name}\""
    if extras:
        line += extras
    lines.append(line)
    for child in tree.get("children", []):
        lines.append(format_tree(child, indent + 1))
    return "\n".join(lines)

def filter_lines(text, pattern, limit=10):
    regex = re.compile(pattern)
    matches = [l for l in text.split("\n") if regex.search(l)]
    return "\n".join(matches[:limit])
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_snapshot.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/brow/snapshot.py tests/test_snapshot.py
git commit -m "feat: snapshot formatting and filtering"
```

---

### Task 5: Daemon Core + Session Routes

**Files:**
- Create: `brow/src/brow/daemon.py`
- Create: `brow/src/brow/routes/sessions.py`
- Create: `brow/tests/test_routes_sessions.py`

- [ ] **Step 1: Write test_routes_sessions.py**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from brow.daemon import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_create_session(client):
    r = await client.post("/sessions", json={"profile": "default", "headless": True})
    assert r.status_code == 200
    assert r.json()["id"] == "1"

@pytest.mark.asyncio
async def test_list_sessions(client):
    await client.post("/sessions", json={"profile": "a", "headless": True})
    r = await client.get("/sessions")
    assert r.status_code == 200
    assert len(r.json()) == 1

@pytest.mark.asyncio
async def test_delete_session(client):
    r = await client.post("/sessions", json={"profile": "default", "headless": True})
    sid = r.json()["id"]
    r = await client.delete(f"/sessions/{sid}")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_delete_nonexistent(client):
    r = await client.delete("/sessions/999")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_status(client):
    r = await client.get("/status")
    assert r.status_code == 200
    assert "sessions" in r.json()
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement daemon.py**

```python
import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from playwright.async_api import async_playwright

from brow.config import DAEMON_HOST, DAEMON_PORT, PID_FILE, LOG_FILE, ensure_dirs
from brow.session import SessionManager
from brow.profiles import ProfileManager

def create_app():
    manager = SessionManager()
    profiles = ProfileManager()
    pw_instance = {}

    @asynccontextmanager
    async def lifespan(app):
        pw = await async_playwright().start()
        pw_instance["pw"] = pw
        app.state.pw = pw
        app.state.manager = manager
        app.state.profiles = profiles
        yield
        await manager.close_all()
        await pw.stop()

    app = FastAPI(lifespan=lifespan)

    from brow.routes.sessions import router as sessions_router
    from brow.routes.browser import router as browser_router
    from brow.routes.pages import router as pages_router
    from brow.routes.profiles import router as profiles_router
    from brow.routes.eval import router as eval_router

    app.include_router(sessions_router)
    app.include_router(browser_router)
    app.include_router(pages_router)
    app.include_router(profiles_router)
    app.include_router(eval_router)

    @app.get("/status")
    async def status():
        return {"sessions": len(manager.sessions), "status": "running"}

    return app

def run_daemon(host=None, port=None):
    ensure_dirs()
    host = host or DAEMON_HOST
    port = port or DAEMON_PORT
    PID_FILE.write_text(str(os.getpid()))
    try:
        uvicorn.run(create_app(), host=host, port=port, log_level="warning")
    finally:
        PID_FILE.unlink(missing_ok=True)

def stop_daemon():
    if not PID_FILE.exists():
        return False
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)
    return True

def daemon_running():
    if not PID_FILE.exists():
        return False
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return False
```

- [ ] **Step 4: Implement routes/sessions.py**

```python
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/sessions", tags=["sessions"])

class CreateSession(BaseModel):
    profile: str = "default"
    headless: bool = True

@router.post("")
async def create(req: Request, body: CreateSession):
    mgr = req.app.state.manager
    profiles = req.app.state.profiles
    pw = req.app.state.pw
    try:
        sid = mgr.create(body.profile, body.headless)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    session = mgr.get(sid)
    user_data_dir = profiles.get_profile_dir(body.profile)
    await session.launch(pw, user_data_dir)
    return {"id": sid, "profile": body.profile}

@router.get("")
async def list_sessions(req: Request):
    return req.app.state.manager.list()

@router.delete("/{sid}")
async def delete(req: Request, sid: str):
    mgr = req.app.state.manager
    try:
        session = mgr.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")
    await session.close()
    mgr.delete(sid)
    return {"deleted": sid}
```

- [ ] **Step 5: Create stub routers for browser, pages, profiles, eval**

Each just:
```python
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 6: Run tests, verify pass**

Run: `pytest tests/test_routes_sessions.py -v`

- [ ] **Step 7: Commit**

```bash
git add src/brow/daemon.py src/brow/routes/ tests/test_routes_sessions.py
git commit -m "feat: daemon core with session CRUD routes"
```

---

### Task 6: Browser Routes (Navigation + Observation + Interaction)

**Files:**
- Create: `brow/src/brow/routes/browser.py`
- Create: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write test_routes_browser.py**

Tests for navigate, snapshot, screenshot, html, click, fill, type, key, hover, scroll, wait, url, logs. Use the ASGI test client from Task 5. Each test creates a session first, navigates to a data URL, then tests the action.

```python
import pytest
from httpx import AsyncClient, ASGITransport
from brow.daemon import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
async def session_id(client):
    r = await client.post("/sessions", json={"profile": "test", "headless": True})
    return r.json()["id"]

@pytest.mark.asyncio
async def test_navigate(client, session_id):
    r = await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hello</h1>"})
    assert r.status_code == 200
    assert "url" in r.json()

@pytest.mark.asyncio
async def test_url(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hi</h1>"})
    r = await client.get(f"/browser/{session_id}/url")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_snapshot(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hello</h1>"})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    assert "tree" in r.json()

@pytest.mark.asyncio
async def test_click(client, session_id):
    html = "data:text/html,<button id='btn'>Click</button>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/click", json={"selector": "#btn"})
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_fill(client, session_id):
    html = "data:text/html,<input id='inp' type='text'/>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/fill", json={"selector": "#inp", "value": "hello"})
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_screenshot(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hi</h1>"})
    r = await client.post(f"/browser/{session_id}/screenshot", json={})
    assert r.status_code == 200
    assert "path" in r.json()

@pytest.mark.asyncio
async def test_html(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<p>Content</p>"})
    r = await client.get(f"/browser/{session_id}/html")
    assert r.status_code == 200
    assert "html" in r.json()

@pytest.mark.asyncio
async def test_logs(client, session_id):
    r = await client.get(f"/browser/{session_id}/logs")
    assert r.status_code == 200
    assert "logs" in r.json()
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement routes/browser.py**

```python
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from brow.config import SCREENSHOTS_DIR, DEFAULT_TIMEOUT, ensure_dirs
from brow.snapshot import format_tree, filter_lines

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

def _get_session(req, sid):
    try:
        return req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")

def _get_page(session):
    page = session.page
    if not page:
        raise HTTPException(400, "No active page")
    return page

class NavigateReq(BaseModel):
    url: str
    timeout: int = DEFAULT_TIMEOUT

class WaitReq(BaseModel):
    selector: Optional[str] = None
    load: bool = False
    timeout: int = DEFAULT_TIMEOUT

class ClickReq(BaseModel):
    selector: str
    timeout: int = DEFAULT_TIMEOUT

class FillReq(BaseModel):
    selector: str
    value: str
    timeout: int = DEFAULT_TIMEOUT

class TypeReq(BaseModel):
    text: str

class KeyReq(BaseModel):
    key: str

class HoverReq(BaseModel):
    selector: str
    timeout: int = DEFAULT_TIMEOUT

class ScrollReq(BaseModel):
    pixels: int = 0
    selector: Optional[str] = None

class DragReq(BaseModel):
    source: str
    target: str

class UploadReq(BaseModel):
    selector: str
    filepath: str

class ScreenshotReq(BaseModel):
    full: bool = False
    path: Optional[str] = None

class SnapshotQuery(BaseModel):
    search: Optional[str] = None
    locator: Optional[str] = None

@router.post("/navigate")
async def navigate(req: Request, sid: str, body: NavigateReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    r = await page.goto(body.url, timeout=body.timeout)
    return {"url": page.url, "status": r.status if r else None}

@router.post("/wait")
async def wait(req: Request, sid: str, body: WaitReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    if body.load:
        await page.wait_for_load_state(timeout=body.timeout)
    elif body.selector:
        await page.wait_for_selector(body.selector, timeout=body.timeout)
    return {"ok": True}

@router.get("/url")
async def get_url(req: Request, sid: str):
    session = _get_session(req, sid)
    page = _get_page(session)
    return {"url": page.url}

@router.get("/snapshot")
async def snapshot(req: Request, sid: str, search: Optional[str] = None, locator: Optional[str] = None):
    session = _get_session(req, sid)
    page = _get_page(session)
    if locator:
        element = page.locator(locator)
        tree = await element.evaluate("el => el.ariaDescription")
    else:
        tree = await page.accessibility.snapshot()
    formatted = format_tree(tree)
    if search:
        formatted = filter_lines(formatted, search)
    return {"tree": formatted}

@router.post("/screenshot")
async def screenshot(req: Request, sid: str, body: ScreenshotReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    ensure_dirs()
    if body.path:
        path = Path(body.path)
    else:
        path = SCREENSHOTS_DIR / f"{sid}-{int(time.time())}.png"
    await page.screenshot(path=str(path), full_page=body.full)
    return {"path": str(path)}

@router.get("/html")
async def get_html(req: Request, sid: str, locator: Optional[str] = None, search: Optional[str] = None):
    session = _get_session(req, sid)
    page = _get_page(session)
    if locator:
        el = page.locator(locator)
        html = await el.inner_html()
    else:
        html = await page.content()
    if search:
        html = filter_lines(html, search)
    return {"html": html}

@router.get("/logs")
async def get_logs(req: Request, sid: str, search: Optional[str] = None, count: int = 50):
    session = _get_session(req, sid)
    logs = session.state.get("console_logs", [])
    text = "\n".join(logs[-count:])
    if search:
        text = filter_lines(text, search)
    return {"logs": text}

@router.post("/click")
async def click(req: Request, sid: str, body: ClickReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.click(body.selector, timeout=body.timeout)
    return {"ok": True}

@router.post("/fill")
async def fill(req: Request, sid: str, body: FillReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.fill(body.selector, body.value, timeout=body.timeout)
    return {"ok": True}

@router.post("/type")
async def type_text(req: Request, sid: str, body: TypeReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.keyboard.type(body.text)
    return {"ok": True}

@router.post("/key")
async def press_key(req: Request, sid: str, body: KeyReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.keyboard.press(body.key)
    return {"ok": True}

@router.post("/hover")
async def hover(req: Request, sid: str, body: HoverReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.hover(body.selector, timeout=body.timeout)
    return {"ok": True}

@router.post("/scroll")
async def scroll(req: Request, sid: str, body: ScrollReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    if body.selector:
        await page.locator(body.selector).scroll_into_view_if_needed()
    else:
        await page.evaluate(f"window.scrollBy(0, {body.pixels})")
    return {"ok": True}

@router.post("/drag")
async def drag(req: Request, sid: str, body: DragReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.drag_and_drop(body.source, body.target)
    return {"ok": True}

@router.post("/upload")
async def upload(req: Request, sid: str, body: UploadReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.set_input_files(body.selector, body.filepath)
    return {"ok": True}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_routes_browser.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/brow/routes/browser.py tests/test_routes_browser.py
git commit -m "feat: browser routes - navigation, observation, interaction"
```

---

### Task 7: Pages Routes

**Files:**
- Create: `brow/src/brow/routes/pages.py`
- Create: `brow/tests/test_routes_pages.py`

- [ ] **Step 1: Write test_routes_pages.py**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from brow.daemon import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
async def session_id(client):
    r = await client.post("/sessions", json={"profile": "test", "headless": True})
    return r.json()["id"]

@pytest.mark.asyncio
async def test_list_pages(client, session_id):
    r = await client.get(f"/pages/{session_id}")
    assert r.status_code == 200
    assert isinstance(r.json()["pages"], list)

@pytest.mark.asyncio
async def test_new_page(client, session_id):
    r = await client.post(f"/pages/{session_id}/new", json={})
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_switch_page(client, session_id):
    await client.post(f"/pages/{session_id}/new", json={})
    r = await client.post(f"/pages/{session_id}/switch", json={"index": 0})
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement routes/pages.py**

```python
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/pages/{sid}", tags=["pages"])

def _get_session(req, sid):
    try:
        return req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")

class NewPageReq(BaseModel):
    url: Optional[str] = None

class SwitchPageReq(BaseModel):
    index: int

@router.get("")
async def list_pages(req: Request, sid: str):
    session = _get_session(req, sid)
    pages = [{"index": i, "url": p.url} for i, p in enumerate(session.pages)]
    return {"pages": pages}

@router.post("/new")
async def new_page(req: Request, sid: str, body: NewPageReq):
    session = _get_session(req, sid)
    page = await session.context.new_page()
    if body.url:
        await page.goto(body.url)
    return {"index": len(session.pages) - 1, "url": page.url}

@router.post("/close")
async def close_page(req: Request, sid: str, index: Optional[int] = None):
    session = _get_session(req, sid)
    pages = session.pages
    idx = index if index is not None else len(pages) - 1
    if idx < 0 or idx >= len(pages):
        raise HTTPException(400, f"Page index {idx} out of range")
    await pages[idx].close()
    return {"closed": idx}

@router.post("/switch")
async def switch_page(req: Request, sid: str, body: SwitchPageReq):
    session = _get_session(req, sid)
    pages = session.pages
    if body.index < 0 or body.index >= len(pages):
        raise HTTPException(400, f"Page index {body.index} out of range")
    await pages[body.index].bring_to_front()
    return {"active": body.index, "url": pages[body.index].url}
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/brow/routes/pages.py tests/test_routes_pages.py
git commit -m "feat: page management routes"
```

---

### Task 8: Profiles & State Routes

**Files:**
- Create: `brow/src/brow/routes/profiles.py`
- Create: `brow/tests/test_routes_profiles.py`

- [ ] **Step 1: Write test_routes_profiles.py**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from brow.daemon import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_list_profiles(client):
    r = await client.get("/profiles")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_delete_profile_nonexistent(client):
    r = await client.delete("/profiles/nope")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_list_states(client):
    r = await client.get("/states")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_save_and_restore_state(client):
    r = await client.post("/sessions", json={"profile": "test", "headless": True})
    sid = r.json()["id"]
    r = await client.post(f"/states/save", json={"name": "test-state", "session_id": sid})
    assert r.status_code == 200
    r = await client.get("/states")
    assert "test-state" in r.json()["states"]
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement routes/profiles.py**

```python
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["profiles"])

@router.get("/profiles")
async def list_profiles(req: Request):
    return {"profiles": req.app.state.profiles.list()}

@router.delete("/profiles/{name}")
async def delete_profile(req: Request, name: str):
    try:
        req.app.state.profiles.delete(name)
    except KeyError:
        raise HTTPException(404, f"Profile '{name}' not found")
    return {"deleted": name}

class SaveStateReq(BaseModel):
    name: str
    session_id: str

class RestoreStateReq(BaseModel):
    name: str
    session_id: str

@router.post("/states/save")
async def save_state(req: Request, body: SaveStateReq):
    mgr = req.app.state.manager
    try:
        session = mgr.get(body.session_id)
    except KeyError:
        raise HTTPException(404, f"Session {body.session_id} not found")
    state = await session.context.storage_state()
    req.app.state.profiles.save_state(body.name, state)
    return {"saved": body.name}

@router.post("/states/restore")
async def restore_state(req: Request, body: RestoreStateReq):
    mgr = req.app.state.manager
    profiles = req.app.state.profiles
    try:
        session = mgr.get(body.session_id)
    except KeyError:
        raise HTTPException(404, f"Session {body.session_id} not found")
    try:
        state = profiles.load_state(body.name)
    except FileNotFoundError:
        raise HTTPException(404, f"State '{body.name}' not found")
    if state.get("cookies"):
        await session.context.add_cookies(state["cookies"])
    return {"restored": body.name}

@router.get("/states")
async def list_states(req: Request):
    return {"states": req.app.state.profiles.list_states()}
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/brow/routes/profiles.py tests/test_routes_profiles.py
git commit -m "feat: profile and state management routes"
```

---

### Task 9: Eval Route

**Files:**
- Create: `brow/src/brow/routes/eval.py`
- Create: `brow/tests/test_routes_eval.py`

- [ ] **Step 1: Write test_routes_eval.py**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from brow.daemon import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
async def session_id(client):
    r = await client.post("/sessions", json={"profile": "test", "headless": True})
    return r.json()["id"]

@pytest.mark.asyncio
async def test_eval_simple(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hi</h1>"})
    r = await client.post(f"/eval/{session_id}", json={"code": "result = await page.title()"})
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_eval_state(client, session_id):
    r = await client.post(f"/eval/{session_id}", json={"code": "state['x'] = 42"})
    assert r.status_code == 200
    r = await client.post(f"/eval/{session_id}", json={"code": "result = state['x']"})
    assert r.json()["result"] == 42

@pytest.mark.asyncio
async def test_eval_error(client, session_id):
    r = await client.post(f"/eval/{session_id}", json={"code": "raise ValueError('boom')"})
    assert r.status_code == 400
    assert "boom" in r.json()["detail"]
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement routes/eval.py**

```python
import asyncio
import io
import sys
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from brow.config import DEFAULT_TIMEOUT

router = APIRouter(prefix="/eval/{sid}", tags=["eval"])

class EvalReq(BaseModel):
    code: str
    timeout: int = DEFAULT_TIMEOUT

@router.post("")
async def eval_code(req: Request, sid: str, body: EvalReq):
    try:
        session = req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")

    page = session.page
    context = session.context
    sandbox = {
        "page": page,
        "context": context,
        "browser": session.browser,
        "state": session.state,
        "pages": session.pages,
        "asyncio": asyncio,
    }

    stdout_capture = io.StringIO()
    code = f"async def __eval__():\n"
    for line in body.code.split("\n"):
        code += f"    {line}\n"

    try:
        exec(compile(code, "<eval>", "exec"), sandbox)
        old_stdout = sys.stdout
        sys.stdout = stdout_capture
        try:
            await asyncio.wait_for(sandbox["__eval__"](), timeout=body.timeout / 1000)
        finally:
            sys.stdout = old_stdout
    except asyncio.TimeoutError:
        raise HTTPException(408, "Eval timed out")
    except Exception as e:
        raise HTTPException(400, str(e))

    return {
        "result": sandbox.get("result"),
        "stdout": stdout_capture.getvalue(),
    }
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/brow/routes/eval.py tests/test_routes_eval.py
git commit -m "feat: eval escape hatch route"
```

---

### Task 10: HTTP Client

**Files:**
- Create: `brow/src/brow/client.py`
- Create: `brow/tests/test_client.py`

- [ ] **Step 1: Write test_client.py**

```python
import pytest
from unittest.mock import AsyncMock, patch
from brow.client import BrowClient

@pytest.fixture
def client():
    return BrowClient()

@pytest.mark.asyncio
async def test_post(client):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "1"}
    mock_resp.raise_for_status = lambda: None
    with patch.object(client._client, "post", return_value=mock_resp):
        result = await client.post("/sessions", json={"profile": "default"})
        assert result == {"id": "1"}

@pytest.mark.asyncio
async def test_get(client):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "running"}
    mock_resp.raise_for_status = lambda: None
    with patch.object(client._client, "get", return_value=mock_resp):
        result = await client.get("/status")
        assert result == {"status": "running"}

@pytest.mark.asyncio
async def test_error_handling(client):
    mock_resp = AsyncMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "not found"}
    mock_resp.raise_for_status.side_effect = Exception("404")
    with patch.object(client._client, "get", return_value=mock_resp):
        with pytest.raises(Exception):
            await client.get("/nope")
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement client.py**

```python
import httpx
from brow.config import DAEMON_URL

class BrowClient:
    def __init__(self, base_url=None):
        self._client = httpx.AsyncClient(
            base_url=base_url or DAEMON_URL,
            timeout=60.0,
        )

    async def get(self, path, **kwargs):
        r = await self._client.get(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def post(self, path, **kwargs):
        r = await self._client.post(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def delete(self, path, **kwargs):
        r = await self._client.delete(path, **kwargs)
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/brow/client.py tests/test_client.py
git commit -m "feat: HTTP client for CLI-daemon communication"
```

---

### Task 11: CLI

**Files:**
- Create: `brow/src/brow/cli.py`
- Create: `brow/tests/test_cli.py`

- [ ] **Step 1: Write test_cli.py**

Test the CLI using typer.testing.CliRunner against the Typer app. Tests will mock the HTTP client calls.

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typer.testing import CliRunner
from brow.cli import app

runner = CliRunner()

def mock_client_response(data):
    async def mock_fn(*args, **kwargs):
        return data
    return mock_fn

def test_daemon_status():
    with patch("brow.cli.daemon_running", return_value=True), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"status": "running", "sessions": 0}
        result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0

def test_session_new():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"id": "1", "profile": "default"}
        result = runner.invoke(app, ["session", "new"])
        assert result.exit_code == 0
        assert "1" in result.stdout

def test_session_list():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = [{"id": "1", "profile": "default", "headless": True, "pages": 1}]
        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0

def test_navigate():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"url": "https://example.com", "status": 200}
        result = runner.invoke(app, ["-s", "1", "navigate", "https://example.com"])
        assert result.exit_code == 0

def test_snapshot():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"tree": "heading \"Hello\""}
        result = runner.invoke(app, ["-s", "1", "snapshot"])
        assert result.exit_code == 0

def test_click():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["-s", "1", "click", "#btn"])
        assert result.exit_code == 0

def test_eval():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"result": 42, "stdout": ""}
        result = runner.invoke(app, ["-s", "1", "eval", "result = 42"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement cli.py**

```python
import asyncio
import subprocess
import sys
import time
from typing import Optional

import typer

from brow.client import BrowClient
from brow.config import DAEMON_HOST, DAEMON_PORT, DAEMON_URL
from brow.daemon import daemon_running, run_daemon, stop_daemon

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

session_opt = typer.Option(None, "-s", "--session", help="Session ID")

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def _client():
    return BrowClient()

def ensure_daemon():
    if daemon_running():
        return
    subprocess.Popen(
        [sys.executable, "-m", "brow.daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(30):
        time.sleep(0.2)
        if daemon_running():
            return
    typer.echo("Failed to start daemon", err=True)
    raise typer.Exit(1)

# -- Daemon --

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

# -- Sessions --

@session_app.command("new")
def session_new(profile: str = "default", headed: bool = False):
    ensure_daemon()
    c = _client()
    result = run_async(c.post("/sessions", json={"profile": profile, "headless": not headed}))
    typer.echo(result["id"])

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

# -- Navigation --

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

# -- Observation --

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
def screenshot_cmd(full: bool = False, path: Optional[str] = None, s: Optional[str] = session_opt):
    ensure_daemon()
    c = _client()
    result = run_async(c.post(f"/browser/{s}/screenshot", json={"full": full, "path": path}))
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

# -- Interaction --

@app.command("click")
def click_cmd(selector: str, s: Optional[str] = session_opt, timeout: int = 30000):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/click", json={"selector": selector, "timeout": timeout}))

@app.command("fill")
def fill_cmd(selector: str, value: str, s: Optional[str] = session_opt, timeout: int = 30000):
    ensure_daemon()
    c = _client()
    run_async(c.post(f"/browser/{s}/fill", json={"selector": selector, "value": value, "timeout": timeout}))

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

# -- Pages --

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

# -- Profiles --

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

# -- States --

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
    for s in result["states"]:
        typer.echo(s)

# -- Eval --

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
```

- [ ] **Step 4: Add `__main__.py` for `python -m brow.daemon`**

Create `src/brow/__main__.py`:
```python
import sys
from brow.daemon import run_daemon

if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else None
    run_daemon(port=port)
```

- [ ] **Step 5: Run tests, verify pass**

Run: `pytest tests/test_cli.py -v`

- [ ] **Step 6: Commit**

```bash
git add src/brow/cli.py src/brow/__main__.py tests/test_cli.py
git commit -m "feat: complete CLI with all commands"
```

---

### Task 12: Console Log Capture + Integration Wiring

**Files:**
- Modify: `brow/src/brow/session.py` (add console listener on launch)

- [ ] **Step 1: Add console log capture to session launch**

In `session.py`, after `launch_persistent_context`, add:
```python
self.state["console_logs"] = []
page = self.context.pages[0] if self.context.pages else await self.context.new_page()
page.on("console", lambda msg: self.state["console_logs"].append(f"[{msg.type}] {msg.text}"))
```

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: console log capture in sessions"
```

---

### Task 13: Final Integration Test + README

**Files:**
- Create: `brow/tests/test_integration.py`
- Create: `brow/README.md`

- [ ] **Step 1: Write integration test**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from brow.daemon import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_full_workflow(client):
    r = await client.post("/sessions", json={"profile": "integration", "headless": True})
    assert r.status_code == 200
    sid = r.json()["id"]

    r = await client.post(f"/browser/{sid}/navigate", json={"url": "data:text/html,<h1>Test</h1><button id='b'>Go</button><input id='i'/>"})
    assert r.status_code == 200

    r = await client.get(f"/browser/{sid}/snapshot")
    assert r.status_code == 200
    assert "Test" in r.json()["tree"]

    r = await client.post(f"/browser/{sid}/click", json={"selector": "#b"})
    assert r.status_code == 200

    r = await client.post(f"/browser/{sid}/fill", json={"selector": "#i", "value": "hello"})
    assert r.status_code == 200

    r = await client.post(f"/browser/{sid}/screenshot", json={})
    assert r.status_code == 200

    r = await client.get(f"/browser/{sid}/html")
    assert r.status_code == 200
    assert "Test" in r.json()["html"]

    r = await client.post(f"/eval/{sid}", json={"code": "result = await page.title()"})
    assert r.status_code == 200

    r = await client.post(f"/states/save", json={"name": "int-test", "session_id": sid})
    assert r.status_code == 200

    r = await client.delete(f"/sessions/{sid}")
    assert r.status_code == 200
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`

- [ ] **Step 3: Run full suite**

Run: `pytest -v`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: integration tests and README"
```
