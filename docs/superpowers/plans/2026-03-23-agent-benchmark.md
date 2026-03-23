# Agent Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a benchmark framework that measures agent performance (tokens, tool calls, success rate, error recovery, wall-clock time) when using brow CLI vs MCP Playwright.

**Architecture:** Claude API harness with tool call interception, local fixture server for reproducible tasks, YAML task definitions, markdown reporter. All code lives in `benchmarks/` inside the brow repo.

**Tech Stack:** Python 3.12+, anthropic SDK, FastAPI (fixture server), PyYAML, mcp (for MCP Playwright client)

---

## File Structure

```
benchmarks/
  __init__.py
  run.py                      # CLI entry point (argparse)
  requirements.txt            # Benchmark-specific dependencies
  harness/
    __init__.py
    config.py                 # BenchmarkConfig dataclass, pricing, defaults
    metrics.py                # RunResult, ToolCallRecord dataclasses
    agent.py                  # Claude API conversation loop with tool interception
    tools_brow.py             # Brow tool schemas + executor
    tools_mcp.py              # MCP Playwright tool schemas + executor
    tools_common.py           # submit_answer tool shared by both backends
    judge.py                  # Success criteria evaluation
    runner.py                 # Orchestrates runs (randomization, alternation, warmup)
    reporter.py               # Generates markdown + JSON reports
    server.py                 # Fixture server lifecycle management
  fixtures/
    app.py                    # FastAPI fixture app with all endpoints
    static/
      search.html             # Task 1: search results page
      multipage/
        page1.html            # Task 3: multi-page nav
        page2.html
        page3.html
      catalog.html            # Task 6: e-commerce product catalog
      wiki/
        index.html            # Task 7: wiki-style info lookup
        topic.html
      large.html              # Task 8: 500+ element page
      steps.html              # Task 10: rapid multi-step form wizard
  tasks/
    search-extract.yaml
    form-fill.yaml
    multi-page-nav.yaml
    login-auth.yaml
    dynamic-content.yaml
    ecommerce-search.yaml
    info-lookup.yaml
    large-snapshot.yaml
    error-recovery.yaml
    rapid-multi-step.yaml
  tests/
    __init__.py
    test_config.py
    test_metrics.py
    test_judge.py
    test_tools_common.py
    test_server.py
    test_reporter.py
    test_runner.py
    test_agent.py
```

---

### Task 1: Config and Metrics Data Models

**Files:**
- Create: `benchmarks/__init__.py`
- Create: `benchmarks/harness/__init__.py`
- Create: `benchmarks/harness/config.py`
- Create: `benchmarks/harness/metrics.py`
- Create: `benchmarks/tests/__init__.py`
- Create: `benchmarks/tests/test_config.py`
- Create: `benchmarks/tests/test_metrics.py`

- [ ] **Step 1: Write failing test for BenchmarkConfig**

```python
# benchmarks/tests/test_config.py
import os
from benchmarks.harness.config import BenchmarkConfig

def test_default_config():
    cfg = BenchmarkConfig()
    assert cfg.model == "claude-sonnet-4-20250514"
    assert cfg.runs == 3
    assert cfg.warmup == 1
    assert cfg.backends == ["brow", "mcp-playwright"]
    assert cfg.tasks_dir.name == "tasks"
    assert isinstance(cfg.pricing, dict)

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    cfg = BenchmarkConfig()
    assert cfg.api_key == "test-key"

def test_config_cost_estimate():
    cfg = BenchmarkConfig()
    cost = cfg.estimate_cost(input_tokens=1000, output_tokens=500)
    assert isinstance(cost, float)
    assert cost > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement config.py**

```python
# benchmarks/__init__.py
# (empty)

# benchmarks/harness/__init__.py
# (empty)

# benchmarks/tests/__init__.py
# (empty)

# benchmarks/harness/config.py
import os
from dataclasses import dataclass, field
from pathlib import Path

BENCHMARKS_DIR = Path(__file__).parent.parent

@dataclass
class BenchmarkConfig:
    model: str = "claude-sonnet-4-20250514"
    runs: int = 3
    warmup: int = 1
    backends: list = field(default_factory=lambda: ["brow", "mcp-playwright"])
    tasks_dir: Path = field(default_factory=lambda: BENCHMARKS_DIR / "tasks")
    output_dir: Path = field(default_factory=lambda: BENCHMARKS_DIR / "results")
    include_live: bool = False
    fixture_port: int = 0
    pricing: dict = field(default_factory=lambda: {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
        "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},
    })

    @property
    def api_key(self):
        return os.environ.get("ANTHROPIC_API_KEY", "")

    def estimate_cost(self, input_tokens, output_tokens):
        rates = self.pricing.get(self.model, {"input": 3.0, "output": 15.0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for metrics**

```python
# benchmarks/tests/test_metrics.py
from benchmarks.harness.metrics import RunResult, ToolCallRecord, aggregate_results

def test_tool_call_record():
    rec = ToolCallRecord(
        name="navigate", input_tokens=100, output_tokens=50,
        latency_ms=500, response_bytes=1024, success=True, error=None
    )
    assert rec.name == "navigate"
    assert rec.success is True

def test_run_result_total_tokens():
    r = RunResult(
        task_id="test", backend="brow", model="claude-sonnet-4-20250514",
        success=True, total_input_tokens=1000, total_output_tokens=500,
        tool_calls=3, tool_call_log=[], wall_clock_ms=5000,
        errors=[], error_recoveries=0, final_output={},
        run_id="r1", timestamp="2026-03-23T00:00:00", brow_version="0.1.4",
        conversation_turns=5
    )
    assert r.total_tokens == 1500

def test_aggregate_results():
    results = [
        RunResult(
            task_id="t1", backend="brow", model="m", success=True,
            total_input_tokens=1000, total_output_tokens=500, tool_calls=5,
            tool_call_log=[], wall_clock_ms=3000, errors=[], error_recoveries=0,
            final_output={}, run_id="r1", timestamp="t", brow_version="v",
            conversation_turns=5
        ),
        RunResult(
            task_id="t1", backend="brow", model="m", success=True,
            total_input_tokens=1200, total_output_tokens=600, tool_calls=7,
            tool_call_log=[], wall_clock_ms=4000, errors=[], error_recoveries=0,
            final_output={}, run_id="r2", timestamp="t", brow_version="v",
            conversation_turns=6
        ),
    ]
    agg = aggregate_results(results)
    assert agg["mean_tokens"] == 1650.0
    assert agg["mean_tool_calls"] == 6.0
    assert agg["success_rate"] == 1.0
    assert agg["n"] == 2
```

- [ ] **Step 6: Implement metrics.py**

```python
# benchmarks/harness/metrics.py
import statistics
from dataclasses import dataclass, field

@dataclass
class ToolCallRecord:
    name: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    response_bytes: int
    success: bool
    error: str | None

@dataclass
class RunResult:
    task_id: str
    backend: str
    model: str
    success: bool
    total_input_tokens: int
    total_output_tokens: int
    tool_calls: int
    tool_call_log: list[ToolCallRecord]
    wall_clock_ms: int
    errors: list[str]
    error_recoveries: int
    final_output: dict
    run_id: str
    timestamp: str
    brow_version: str
    conversation_turns: int

    @property
    def total_tokens(self):
        return self.total_input_tokens + self.total_output_tokens

def aggregate_results(results: list[RunResult]) -> dict:
    tokens = [r.total_tokens for r in results]
    input_tokens = [r.total_input_tokens for r in results]
    output_tokens = [r.total_output_tokens for r in results]
    calls = [r.tool_calls for r in results]
    times = [r.wall_clock_ms for r in results]
    successes = [r.success for r in results]
    n = len(results)
    return {
        "n": n,
        "mean_tokens": statistics.mean(tokens),
        "stddev_tokens": statistics.stdev(tokens) if n > 1 else 0.0,
        "mean_input_tokens": statistics.mean(input_tokens),
        "mean_output_tokens": statistics.mean(output_tokens),
        "mean_tool_calls": statistics.mean(calls),
        "stddev_tool_calls": statistics.stdev(calls) if n > 1 else 0.0,
        "mean_wall_clock_ms": statistics.mean(times),
        "stddev_wall_clock_ms": statistics.stdev(times) if n > 1 else 0.0,
        "success_rate": sum(successes) / n,
        "mean_errors": statistics.mean([len(r.errors) for r in results]),
        "mean_recoveries": statistics.mean([r.error_recoveries for r in results]),
    }
```

- [ ] **Step 7: Run all tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_config.py benchmarks/tests/test_metrics.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add benchmarks/__init__.py benchmarks/harness/__init__.py benchmarks/harness/config.py benchmarks/harness/metrics.py benchmarks/tests/__init__.py benchmarks/tests/test_config.py benchmarks/tests/test_metrics.py
git commit -m "feat(bench): add config and metrics data models"
```

---

### Task 2: Fixture Server and Static Pages

**Files:**
- Create: `benchmarks/fixtures/__init__.py`
- Create: `benchmarks/fixtures/app.py`
- Create: `benchmarks/fixtures/static/search.html`
- Create: `benchmarks/fixtures/static/form.html`
- Create: `benchmarks/fixtures/static/multipage/page1.html`
- Create: `benchmarks/fixtures/static/multipage/page2.html`
- Create: `benchmarks/fixtures/static/multipage/page3.html`
- Create: `benchmarks/fixtures/static/catalog.html`
- Create: `benchmarks/fixtures/static/wiki/index.html`
- Create: `benchmarks/fixtures/static/wiki/topic.html`
- Create: `benchmarks/fixtures/static/large.html`
- Create: `benchmarks/fixtures/static/steps.html`
- Create: `benchmarks/harness/server.py`
- Create: `benchmarks/tests/test_server.py`

- [ ] **Step 1: Write failing test for fixture server**

```python
# benchmarks/tests/test_server.py
import httpx
import pytest
from benchmarks.harness.server import FixtureServer

@pytest.fixture
async def server():
    s = FixtureServer(port=0)
    await s.start()
    yield s
    await s.stop()

@pytest.mark.asyncio
async def test_server_starts_and_serves_static(server):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{server.base_url}/static/search.html")
        assert r.status_code == 200
        assert "search-results" in r.text

@pytest.mark.asyncio
async def test_form_endpoint(server):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{server.base_url}/form", data={"name": "Test", "email": "t@t.com"})
        assert r.status_code == 200
        assert "confirmation" in r.text.lower()

@pytest.mark.asyncio
async def test_login_flow(server):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{server.base_url}/login", data={"username": "admin", "password": "password123"})
        assert r.status_code == 200
        cookies = r.cookies
        r2 = await client.get(f"{server.base_url}/dashboard", cookies=cookies)
        assert r2.status_code == 200
        assert "dashboard" in r2.text.lower()

@pytest.mark.asyncio
async def test_dynamic_endpoint(server):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{server.base_url}/dynamic")
        assert r.status_code == 200
        assert "dynamic-content" in r.text

@pytest.mark.asyncio
async def test_flaky_endpoint(server):
    async with httpx.AsyncClient() as client:
        responses = []
        for _ in range(20):
            r = await client.get(f"{server.base_url}/flaky")
            responses.append("flaky-element" in r.text)
        assert any(responses) and not all(responses)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_server.py -v`
Expected: FAIL

- [ ] **Step 3: Create static HTML pages**

Create `benchmarks/fixtures/static/search.html`:
```html
<!DOCTYPE html>
<html><head><title>Search Results</title></head>
<body>
<h1>Search Results for "best coffee shops NYC"</h1>
<div id="search-results">
  <div class="result" data-rank="1"><a href="/r/1" class="title">Blue Bottle Coffee</a><span class="rating">4.5</span><p class="snippet">Premium coffee experience in Manhattan</p></div>
  <div class="result" data-rank="2"><a href="/r/2" class="title">Stumptown Coffee Roasters</a><span class="rating">4.4</span><p class="snippet">Portland-born roaster in Greenwich Village</p></div>
  <div class="result" data-rank="3"><a href="/r/3" class="title">Joe Coffee Company</a><span class="rating">4.3</span><p class="snippet">Local NYC chain with great espresso</p></div>
  <div class="result" data-rank="4"><a href="/r/4" class="title">Devocion</a><span class="rating">4.6</span><p class="snippet">Colombian beans roasted in Brooklyn</p></div>
  <div class="result" data-rank="5"><a href="/r/5" class="title">Abraco</a><span class="rating">4.5</span><p class="snippet">Tiny East Village gem with amazing pastries</p></div>
  <div class="result" data-rank="6"><a href="/r/6" class="title">La Cabra</a><span class="rating">4.2</span><p class="snippet">Danish specialty coffee in Soho</p></div>
  <div class="result" data-rank="7"><a href="/r/7" class="title">Sey Coffee</a><span class="rating">4.4</span><p class="snippet">Bushwick roaster with minimalist vibes</p></div>
</div>
</body></html>
```

Create `benchmarks/fixtures/static/form.html`:
```html
<!DOCTYPE html>
<html><head><title>Contact Form</title></head>
<body>
<h1>Contact Us</h1>
<form id="contact-form" action="/form" method="POST">
  <label for="name">Name</label><input type="text" id="name" name="name" required>
  <label for="email">Email</label><input type="email" id="email" name="email" required>
  <label for="subject">Subject</label><select id="subject" name="subject">
    <option value="support">Support</option>
    <option value="sales">Sales</option>
    <option value="other">Other</option>
  </select>
  <label for="message">Message</label><textarea id="message" name="message" required></textarea>
  <button type="submit">Send Message</button>
</form>
</body></html>
```

Create `benchmarks/fixtures/static/multipage/page1.html`:
```html
<!DOCTYPE html>
<html><head><title>Company - About</title></head>
<body>
<nav><a href="/static/multipage/page1.html">About</a> <a href="/static/multipage/page2.html">Team</a> <a href="/static/multipage/page3.html">Contact</a></nav>
<h1>About Us</h1>
<p class="founded">Founded: 2020</p>
<p class="mission">Building tools for the future of AI</p>
</body></html>
```

Create `benchmarks/fixtures/static/multipage/page2.html`:
```html
<!DOCTYPE html>
<html><head><title>Company - Team</title></head>
<body>
<nav><a href="/static/multipage/page1.html">About</a> <a href="/static/multipage/page2.html">Team</a> <a href="/static/multipage/page3.html">Contact</a></nav>
<h1>Our Team</h1>
<div class="member"><span class="name">Alice Chen</span><span class="role">CEO</span></div>
<div class="member"><span class="name">Bob Park</span><span class="role">CTO</span></div>
<div class="member"><span class="name">Carol Wu</span><span class="role">VP Engineering</span></div>
</body></html>
```

Create `benchmarks/fixtures/static/multipage/page3.html`:
```html
<!DOCTYPE html>
<html><head><title>Company - Contact</title></head>
<body>
<nav><a href="/static/multipage/page1.html">About</a> <a href="/static/multipage/page2.html">Team</a> <a href="/static/multipage/page3.html">Contact</a></nav>
<h1>Contact</h1>
<p class="email">hello@example.com</p>
<p class="phone">+1-555-0100</p>
<p class="address">123 Tech Street, San Francisco, CA 94105</p>
</body></html>
```

Create `benchmarks/fixtures/static/catalog.html`:
```html
<!DOCTYPE html>
<html><head><title>Product Catalog</title></head>
<body>
<h1>Electronics Store</h1>
<div class="filters">
  <select id="category"><option value="all">All</option><option value="laptops">Laptops</option><option value="phones">Phones</option></select>
  <select id="sort"><option value="price-asc">Price: Low to High</option><option value="rating-desc">Rating: High to Low</option></select>
</div>
<div id="products">
  <div class="product" data-category="laptops"><h2 class="name">ProBook 15</h2><span class="price">$999</span><span class="rating">4.5</span><p class="desc">15-inch laptop, 16GB RAM</p></div>
  <div class="product" data-category="laptops"><h2 class="name">UltraSlim X</h2><span class="price">$1299</span><span class="rating">4.7</span><p class="desc">13-inch ultralight, 32GB RAM</p></div>
  <div class="product" data-category="phones"><h2 class="name">PhoneMax 15</h2><span class="price">$899</span><span class="rating">4.3</span><p class="desc">6.7-inch display, 256GB</p></div>
  <div class="product" data-category="phones"><h2 class="name">BudgetPhone SE</h2><span class="price">$399</span><span class="rating">4.0</span><p class="desc">5.8-inch display, 128GB</p></div>
  <div class="product" data-category="laptops"><h2 class="name">GameStation Pro</h2><span class="price">$1899</span><span class="rating">4.8</span><p class="desc">17-inch gaming laptop, RTX 4080</p></div>
</div>
</body></html>
```

Create `benchmarks/fixtures/static/wiki/index.html`:
```html
<!DOCTYPE html>
<html><head><title>Wiki - Home</title></head>
<body>
<h1>Knowledge Base</h1>
<ul id="topics">
  <li><a href="/static/wiki/topic.html?id=photosynthesis">Photosynthesis</a></li>
  <li><a href="/static/wiki/topic.html?id=gravity">Gravity</a></li>
  <li><a href="/static/wiki/topic.html?id=turing">Alan Turing</a></li>
</ul>
</body></html>
```

Create `benchmarks/fixtures/static/wiki/topic.html`:
```html
<!DOCTYPE html>
<html><head><title>Wiki - Topic</title></head>
<body>
<h1 id="topic-title">Photosynthesis</h1>
<div id="content">
  <p class="summary">Photosynthesis converts light energy into chemical energy.</p>
  <dl>
    <dt>Discovery Year</dt><dd class="fact" data-key="discovery_year">1779</dd>
    <dt>Discoverer</dt><dd class="fact" data-key="discoverer">Jan Ingenhousz</dd>
    <dt>Key Molecule</dt><dd class="fact" data-key="molecule">Chlorophyll</dd>
  </dl>
</div>
<a href="/static/wiki/index.html">Back to topics</a>
</body></html>
```

Create `benchmarks/fixtures/static/large.html` (generated with Python in the fixture app — see below, served as template):
```html
<!DOCTYPE html>
<html><head><title>Large Page</title></head>
<body>
<h1>Large Page Test</h1>
<div id="content">
<!-- 500+ elements generated server-side -->
</div>
</body></html>
```

Create `benchmarks/fixtures/static/steps.html`:
```html
<!DOCTYPE html>
<html><head><title>Multi-Step Wizard</title></head>
<body>
<h1>Registration Wizard</h1>
<div id="wizard">
  <div class="step" data-step="1"><h2>Step 1: Personal Info</h2><input id="first-name" placeholder="First Name"><input id="last-name" placeholder="Last Name"><button id="next-1">Next</button></div>
  <div class="step" data-step="2" style="display:none"><h2>Step 2: Contact</h2><input id="phone" placeholder="Phone"><input id="city" placeholder="City"><button id="next-2">Next</button></div>
  <div class="step" data-step="3" style="display:none"><h2>Step 3: Preferences</h2><select id="color"><option>Red</option><option>Blue</option><option>Green</option></select><input type="checkbox" id="newsletter"><label for="newsletter">Subscribe</label><button id="next-3">Next</button></div>
  <div class="step" data-step="4" style="display:none"><h2>Step 4: Review</h2><div id="review-data"></div><button id="submit-wizard">Submit</button></div>
  <div class="step" data-step="5" style="display:none"><h2>Registration Complete</h2><p id="confirmation">Thank you for registering!</p></div>
</div>
<script>
document.querySelectorAll('[id^="next-"]').forEach(btn => {
  btn.addEventListener('click', () => {
    const current = btn.closest('.step');
    const next = current.nextElementSibling;
    if (next) { current.style.display='none'; next.style.display='block'; }
    if (next && next.dataset.step === '4') {
      document.getElementById('review-data').textContent =
        'Name: ' + document.getElementById('first-name').value + ' ' + document.getElementById('last-name').value;
    }
  });
});
document.getElementById('submit-wizard').addEventListener('click', () => {
  document.querySelector('[data-step="4"]').style.display='none';
  document.querySelector('[data-step="5"]').style.display='block';
});
</script>
</body></html>
```

- [ ] **Step 4: Implement fixture app**

```python
# benchmarks/fixtures/__init__.py
# (empty)

# benchmarks/fixtures/app.py
import random
from pathlib import Path

from fastapi import FastAPI, Form, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

STATIC_DIR = Path(__file__).parent / "static"

def create_fixture_app():
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    sessions = {}

    @app.post("/form", response_class=HTMLResponse)
    async def form_submit(name: str = Form(...), email: str = Form(...),
                          subject: str = Form("other"), message: str = Form("")):
        return f"""<html><body>
        <h1>Confirmation</h1>
        <p>Thank you, {name}! Your message about '{subject}' has been received.</p>
        <p>We'll reply to {email} shortly.</p>
        </body></html>"""

    @app.post("/login", response_class=HTMLResponse)
    async def login(response: Response, username: str = Form(...), password: str = Form(...)):
        if username == "admin" and password == "password123":
            token = f"session-{random.randint(1000,9999)}"
            sessions[token] = username
            response.set_cookie("auth_token", token)
            return f"""<html><body>
            <h1>Login Successful</h1>
            <p>Welcome, {username}. <a href="/dashboard">Go to Dashboard</a></p>
            </body></html>"""
        return HTMLResponse("<html><body><h1>Login Failed</h1><p>Invalid credentials</p></body></html>", status_code=401)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(auth_token: str = Cookie(None)):
        if auth_token not in sessions:
            return HTMLResponse("<html><body><h1>Unauthorized</h1></body></html>", status_code=401)
        user = sessions[auth_token]
        return f"""<html><body>
        <h1>Dashboard</h1>
        <p>Welcome back, {user}</p>
        <div id="user-data"><span class="username">{user}</span><span class="role">Administrator</span></div>
        <button id="logout">Logout</button>
        </body></html>"""

    @app.get("/dynamic", response_class=HTMLResponse)
    async def dynamic():
        return """<html><head><title>Dynamic Page</title></head>
        <body>
        <h1>Dynamic Content</h1>
        <div id="loading">Loading...</div>
        <div id="dynamic-content" style="display:none">
          <div class="item"><span class="name">Alpha</span><span class="value">100</span></div>
          <div class="item"><span class="name">Beta</span><span class="value">200</span></div>
          <div class="item"><span class="name">Gamma</span><span class="value">300</span></div>
        </div>
        <script>
        setTimeout(() => {
          document.getElementById('loading').style.display='none';
          document.getElementById('dynamic-content').style.display='block';
        }, 2000);
        </script>
        </body></html>"""

    @app.get("/flaky", response_class=HTMLResponse)
    async def flaky():
        show = random.random() > 0.5
        element = '<div id="flaky-element" class="target">Found me!</div>' if show else '<div id="placeholder">Loading...</div>'
        return f"""<html><body>
        <h1>Flaky Page</h1>
        {element}
        <p class="status">{'Element visible' if show else 'Element missing'}</p>
        </body></html>"""

    @app.get("/large", response_class=HTMLResponse)
    async def large():
        items = "\n".join(
            f'<div class="item" data-id="{i}"><span class="label">Item {i}</span>'
            f'<span class="value">{i * 7 % 100}</span>'
            f'<button class="action">Select</button></div>'
            for i in range(550)
        )
        return f"""<html><body>
        <h1>Large Page Test</h1>
        <div id="content">{items}</div>
        </body></html>"""

    return app
```

- [ ] **Step 5: Implement server lifecycle**

```python
# benchmarks/harness/server.py
import asyncio
import socket
import uvicorn

class FixtureServer:
    def __init__(self, port=0):
        self.port = port or self._find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._server = None
        self._task = None

    def _find_free_port(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    async def start(self):
        from benchmarks.fixtures.app import create_fixture_app
        app = create_fixture_app()
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())
        await asyncio.sleep(0.5)

    async def stop(self):
        if self._server:
            self._server.should_exit = True
            if self._task:
                await self._task
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_server.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add benchmarks/fixtures/ benchmarks/harness/server.py benchmarks/tests/test_server.py
git commit -m "feat(bench): add fixture server with static pages and dynamic endpoints"
```

---

### Task 3: Tool Definitions (submit_answer + brow + MCP Playwright)

**Files:**
- Create: `benchmarks/harness/tools_common.py`
- Create: `benchmarks/harness/tools_brow.py`
- Create: `benchmarks/harness/tools_mcp.py`
- Create: `benchmarks/tests/test_tools_common.py`

- [ ] **Step 1: Write failing test for tools_common**

```python
# benchmarks/tests/test_tools_common.py
from benchmarks.harness.tools_common import SUBMIT_ANSWER_TOOL, execute_submit_answer

def test_submit_answer_schema():
    assert SUBMIT_ANSWER_TOOL["name"] == "submit_answer"
    assert "input_schema" in SUBMIT_ANSWER_TOOL
    props = SUBMIT_ANSWER_TOOL["input_schema"]["properties"]
    assert "answer" in props
    assert "confidence" in props

def test_execute_submit_answer():
    result = execute_submit_answer({"answer": {"title": "test"}, "confidence": "high"})
    assert result["done"] is True
    assert result["answer"]["title"] == "test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_tools_common.py -v`
Expected: FAIL

- [ ] **Step 3: Implement tools_common.py**

```python
# benchmarks/harness/tools_common.py
SUBMIT_ANSWER_TOOL = {
    "name": "submit_answer",
    "description": "Submit your final answer for the task. Call this when you have completed the task.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "object", "description": "Structured result matching task requirements"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"], "description": "Your confidence in the answer"},
        },
        "required": ["answer"],
    },
}

def execute_submit_answer(params):
    return {"done": True, "answer": params.get("answer", {}), "confidence": params.get("confidence", "medium")}
```

- [ ] **Step 4: Implement tools_brow.py**

```python
# benchmarks/harness/tools_brow.py
import subprocess
import json

BROW_TOOLS = [
    {
        "name": "brow_session_new",
        "description": "Start a new browser session. Returns session ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "default": "benchmark"},
                "headed": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "brow_navigate",
        "description": "Navigate to a URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["session", "url"],
        },
    },
    {
        "name": "brow_snapshot",
        "description": "Get the accessibility tree of the current page. Fast and token-efficient way to understand page content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "search": {"type": "string", "description": "Regex to filter snapshot lines"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_click",
        "description": "Click an element. Selectors: CSS (#id, .class), text (text=Click Me), role (role=button[name='Save']).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
            },
            "required": ["session", "selector"],
        },
    },
    {
        "name": "brow_fill",
        "description": "Fill an input field with a value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["session", "selector", "value"],
        },
    },
    {
        "name": "brow_type",
        "description": "Type text with keyboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["session", "text"],
        },
    },
    {
        "name": "brow_key",
        "description": "Press a key (Enter, Tab, Escape, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "key": {"type": "string"},
            },
            "required": ["session", "key"],
        },
    },
    {
        "name": "brow_screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "quality": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_wait",
        "description": "Wait for a selector to appear or page to load.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
                "load": {"type": "boolean"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_url",
        "description": "Get the current page URL.",
        "input_schema": {
            "type": "object",
            "properties": {"session": {"type": "string"}},
            "required": ["session"],
        },
    },
    {
        "name": "brow_html",
        "description": "Get page HTML content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "locator": {"type": "string"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_select",
        "description": "Select an option from a dropdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["session", "selector", "value"],
        },
    },
    {
        "name": "brow_scroll",
        "description": "Scroll the page by pixels or to a selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "pixels": {"type": "integer"},
                "selector": {"type": "string"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_hover",
        "description": "Hover over an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "selector": {"type": "string"},
            },
            "required": ["session", "selector"],
        },
    },
]

def execute_brow_tool(name, params):
    cmd_map = {
        "brow_session_new": lambda p: ["brow", "session", "new"] + (["--headed"] if p.get("headed") else []) + (["--profile", p.get("profile", "benchmark")]),
        "brow_navigate": lambda p: ["brow", "-s", p["session"], "navigate", p["url"]],
        "brow_snapshot": lambda p: ["brow", "-s", p["session"], "snapshot"] + (["--search", p["search"]] if p.get("search") else []),
        "brow_click": lambda p: ["brow", "-s", p["session"], "click", p["selector"]],
        "brow_fill": lambda p: ["brow", "-s", p["session"], "fill", p["selector"], p["value"]],
        "brow_type": lambda p: ["brow", "-s", p["session"], "type", p["text"]],
        "brow_key": lambda p: ["brow", "-s", p["session"], "key", p["key"]],
        "brow_screenshot": lambda p: ["brow", "-s", p["session"], "screenshot"] + (["--quality", p["quality"]] if p.get("quality") else []),
        "brow_wait": lambda p: ["brow", "-s", p["session"], "wait"] + ([p["selector"]] if p.get("selector") else []) + (["--load"] if p.get("load") else []),
        "brow_url": lambda p: ["brow", "-s", p["session"], "url"],
        "brow_html": lambda p: ["brow", "-s", p["session"], "html"] + (["--locator", p["locator"]] if p.get("locator") else []),
        "brow_select": lambda p: ["brow", "-s", p["session"], "eval", "await page.select_option(" + json.dumps(p["selector"]) + ", " + json.dumps(p["value"]) + ")"],
        "brow_scroll": lambda p: (["brow", "-s", p["session"], "scroll-to", p["selector"]] if p.get("selector") else ["brow", "-s", p["session"], "scroll", str(p.get("pixels", 0))]),
        "brow_hover": lambda p: ["brow", "-s", p["session"], "hover", p["selector"]],
    }
    builder = cmd_map.get(name)
    if not builder:
        return {"error": f"Unknown tool: {name}"}
    cmd = builder(params)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or f"Exit code {result.returncode}"}
        return {"output": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 5: Implement tools_mcp.py**

```python
# benchmarks/harness/tools_mcp.py
import asyncio
import json
import subprocess
import sys

MCP_TOOLS = [
    {
        "name": "mcp_navigate",
        "description": "Navigate to a URL in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "mcp_snapshot",
        "description": "Get the accessibility snapshot of the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "mcp_click",
        "description": "Click an element on the page using a CSS selector or text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "Human-readable element description"},
                "ref": {"type": "string", "description": "Element reference from snapshot"},
            },
            "required": ["element", "ref"],
        },
    },
    {
        "name": "mcp_fill",
        "description": "Fill an input field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string"},
                "ref": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["element", "ref", "value"],
        },
    },
    {
        "name": "mcp_type",
        "description": "Type text using keyboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "submit": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "mcp_press_key",
        "description": "Press a key.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "mcp_screenshot",
        "description": "Take a screenshot of the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "mcp_hover",
        "description": "Hover over an element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string"},
                "ref": {"type": "string"},
            },
            "required": ["element", "ref"],
        },
    },
    {
        "name": "mcp_select_option",
        "description": "Select an option from a dropdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string"},
                "ref": {"type": "string"},
                "values": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["element", "ref", "values"],
        },
    },
    {
        "name": "mcp_wait",
        "description": "Wait for a condition.",
        "input_schema": {
            "type": "object",
            "properties": {"time": {"type": "integer", "description": "Milliseconds to wait"}},
            "required": ["time"],
        },
    },
    {
        "name": "mcp_evaluate",
        "description": "Execute JavaScript in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {"javascript": {"type": "string"}},
            "required": ["javascript"],
        },
    },
]

MCP_TOOL_NAME_MAP = {
    "mcp_navigate": "browser_navigate",
    "mcp_snapshot": "browser_snapshot",
    "mcp_click": "browser_click",
    "mcp_fill": "browser_fill_form",
    "mcp_type": "browser_type",
    "mcp_press_key": "browser_press_key",
    "mcp_screenshot": "browser_take_screenshot",
    "mcp_hover": "browser_hover",
    "mcp_select_option": "browser_select_option",
    "mcp_wait": "browser_wait_for",
    "mcp_evaluate": "browser_evaluate",
}


class McpPlaywrightClient:
    def __init__(self):
        self._proc = None
        self._request_id = 0

    async def start(self):
        self._proc = await asyncio.create_subprocess_exec(
            "npx", "@anthropic-ai/mcp-playwright",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self._send({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "benchmark", "version": "1.0"},
        }})
        await self._read_response()
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def call_tool(self, mcp_method, params):
        self._request_id += 1
        await self._send({
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": mcp_method, "arguments": params},
        })
        return await self._read_response()

    async def stop(self):
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

    async def _send(self, msg):
        data = json.dumps(msg)
        content = f"Content-Length: {len(data)}\r\n\r\n{data}"
        self._proc.stdin.write(content.encode())
        await self._proc.stdin.drain()

    async def _read_response(self):
        content_length = 0
        while True:
            line = await self._proc.stdout.readline()
            decoded = line.decode().strip()
            if not decoded:
                break
            if decoded.startswith("Content-Length:"):
                content_length = int(decoded.split(":")[1].strip())
        if content_length == 0:
            return {"error": "No Content-Length in MCP response"}
        raw = await self._proc.stdout.readexactly(content_length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "Failed to parse MCP response"}


async def execute_mcp_tool(client: McpPlaywrightClient, name: str, params: dict):
    mcp_method = MCP_TOOL_NAME_MAP.get(name)
    if not mcp_method:
        return {"error": f"Unknown MCP tool: {name}"}
    try:
        response = await client.call_tool(mcp_method, params)
        if "error" in response:
            return {"error": str(response["error"])}
        result = response.get("result", {})
        content = result.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return {"output": "\n".join(text_parts) if text_parts else json.dumps(result)}
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_tools_common.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add benchmarks/harness/tools_common.py benchmarks/harness/tools_brow.py benchmarks/harness/tools_mcp.py benchmarks/tests/test_tools_common.py
git commit -m "feat(bench): add tool definitions for brow, MCP Playwright, and submit_answer"
```

---

### Task 4: Judge (Success Criteria Evaluation)

**Files:**
- Create: `benchmarks/harness/judge.py`
- Create: `benchmarks/tests/test_judge.py`

- [ ] **Step 1: Write failing tests**

```python
# benchmarks/tests/test_judge.py
from benchmarks.harness.judge import evaluate_criteria

def test_structured_output_pass():
    criteria = {"type": "structured_output", "min_fields": ["title", "url"], "min_results": 2}
    answer = {"results": [{"title": "A", "url": "http://a"}, {"title": "B", "url": "http://b"}]}
    assert evaluate_criteria(criteria, answer, {}) is True

def test_structured_output_missing_field():
    criteria = {"type": "structured_output", "min_fields": ["title", "url"], "min_results": 1}
    answer = {"results": [{"title": "A"}]}
    assert evaluate_criteria(criteria, answer, {}) is False

def test_structured_output_too_few():
    criteria = {"type": "structured_output", "min_fields": ["title"], "min_results": 5}
    answer = {"results": [{"title": "A"}, {"title": "B"}]}
    assert evaluate_criteria(criteria, answer, {}) is False

def test_url_match_pass():
    criteria = {"type": "url_match", "pattern": r"example\.com/dashboard"}
    assert evaluate_criteria(criteria, {}, {"url": "https://example.com/dashboard?tab=1"}) is True

def test_url_match_fail():
    criteria = {"type": "url_match", "pattern": r"example\.com/admin"}
    assert evaluate_criteria(criteria, {}, {"url": "https://example.com/dashboard"}) is False

def test_no_errors_pass():
    criteria = {"type": "no_errors"}
    assert evaluate_criteria(criteria, {}, {}, errors=[]) is True

def test_no_errors_fail():
    criteria = {"type": "no_errors"}
    assert evaluate_criteria(criteria, {}, {}, errors=["timeout"]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_judge.py -v`
Expected: FAIL

- [ ] **Step 3: Implement judge.py**

```python
# benchmarks/harness/judge.py
import importlib
import re

def evaluate_criteria(criteria, answer, browser_state, errors=None):
    ctype = criteria["type"]
    if ctype == "structured_output":
        return _check_structured_output(criteria, answer)
    if ctype == "url_match":
        return _check_url_match(criteria, browser_state)
    if ctype == "no_errors":
        return len(errors or []) == 0
    if ctype == "element_visible":
        return browser_state.get("element_visible", False)
    if ctype == "custom":
        return _check_custom(criteria, answer, browser_state)
    return False

def _check_structured_output(criteria, answer):
    min_fields = criteria.get("min_fields", [])
    min_results = criteria.get("min_results", 1)
    results = _find_results_list(answer)
    if len(results) < min_results:
        return False
    for item in results:
        if not all(f in item for f in min_fields):
            return False
    return True

def _find_results_list(answer):
    if isinstance(answer, list):
        return answer
    if isinstance(answer, dict):
        for v in answer.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []

def _check_url_match(criteria, browser_state):
    pattern = criteria.get("pattern", "")
    url = browser_state.get("url", "")
    return bool(re.search(pattern, url))

def _check_custom(criteria, answer, browser_state):
    func_path = criteria.get("function", "")
    module_path, func_name = func_path.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    func = getattr(mod, func_name)
    return func(answer, browser_state)

def evaluate_all(criteria_list, answer, browser_state, errors=None):
    return all(evaluate_criteria(c, answer, browser_state, errors) for c in criteria_list)
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_judge.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/harness/judge.py benchmarks/tests/test_judge.py
git commit -m "feat(bench): add judge for success criteria evaluation"
```

---

### Task 5: Agent Harness (Claude API Conversation Loop)

**Files:**
- Create: `benchmarks/harness/agent.py`
- Create: `benchmarks/tests/test_agent.py`

- [ ] **Step 1: Write failing test for agent**

```python
# benchmarks/tests/test_agent.py
from unittest.mock import AsyncMock, patch, MagicMock
from benchmarks.harness.agent import AgentLoop, build_system_prompt
from benchmarks.harness.config import BenchmarkConfig

def test_build_system_prompt_brow():
    prompt = build_system_prompt("brow", "Find the top 5 coffee shops")
    assert "browser automation agent" in prompt.lower()
    assert "brow" in prompt.lower()
    assert "coffee shops" in prompt

def test_build_system_prompt_mcp():
    prompt = build_system_prompt("mcp-playwright", "Fill the form")
    assert "browser automation agent" in prompt.lower()
    assert "playwright" in prompt.lower()
    assert "form" in prompt

def test_agent_loop_init():
    cfg = BenchmarkConfig()
    loop = AgentLoop(config=cfg, backend="brow", task_description="test task")
    assert loop.backend == "brow"
    assert loop.messages == []
    assert loop.total_input_tokens == 0
    assert loop.total_output_tokens == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_agent.py -v`
Expected: FAIL

- [ ] **Step 3: Implement agent.py**

```python
# benchmarks/harness/agent.py
import time
import json
from dataclasses import dataclass, field

import anthropic

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.metrics import ToolCallRecord
from benchmarks.harness.tools_common import SUBMIT_ANSWER_TOOL, execute_submit_answer
from benchmarks.harness.tools_brow import BROW_TOOLS, execute_brow_tool
from benchmarks.harness.tools_mcp import MCP_TOOLS, MCP_TOOL_NAME_MAP, McpPlaywrightClient, execute_mcp_tool

def _load_brow_skill():
    from pathlib import Path
    skill_path = Path(__file__).parent.parent.parent / "skills" / "brow" / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    return ""

BROW_INSTRUCTIONS = f"""You have access to brow CLI tools for browser automation.
Use brow_session_new to start a session, then use the session ID with other tools.
Use brow_snapshot to read page content (fast, token-efficient).
Selectors: CSS (#id, .class), text (text=Click Me), role (role=button[name='Save']).
When done, call submit_answer with your structured result."""

MCP_INSTRUCTIONS = """You have access to MCP Playwright tools for browser automation.
Use mcp_navigate to go to URLs. Use mcp_snapshot to read the page.
Use element references from snapshots when clicking or filling.
When done, call submit_answer with your structured result."""

def build_system_prompt(backend, task_description):
    if backend == "brow":
        skill_content = _load_brow_skill()
        instructions = BROW_INSTRUCTIONS + ("\n\n" + skill_content if skill_content else "")
    else:
        instructions = MCP_INSTRUCTIONS
    return f"""You are a browser automation agent. Complete the given task using the provided tools.

{instructions}

Do not explain your actions. Execute efficiently with minimal tool calls.

Task: {task_description}"""


class AgentLoop:
    def __init__(self, config: BenchmarkConfig, backend: str, task_description: str):
        self.config = config
        self.backend = backend
        self.system_prompt = build_system_prompt(backend, task_description)
        self.tools = self._get_tools()
        self.messages = []
        self.tool_call_log = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.conversation_turns = 0
        self.errors = []
        self.error_recoveries = 0
        self._last_failed_tool = None
        self._mcp_client = None
        self._brow_session_id = None

    def _get_tools(self):
        base = BROW_TOOLS if self.backend == "brow" else MCP_TOOLS
        return [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in base] + [
            {"name": SUBMIT_ANSWER_TOOL["name"], "description": SUBMIT_ANSWER_TOOL["description"], "input_schema": SUBMIT_ANSWER_TOOL["input_schema"]}
        ]

    async def run(self, max_steps=15, timeout_seconds=120):
        client = anthropic.Anthropic(api_key=self.config.api_key)
        if self.backend == "mcp-playwright":
            self._mcp_client = McpPlaywrightClient()
            await self._mcp_client.start()

        start = time.time()
        self.messages = [{"role": "user", "content": "Begin the task."}]
        final_output = {}

        try:
            for step in range(max_steps):
                if time.time() - start > timeout_seconds:
                    break

                self.conversation_turns += 1
                response = client.messages.create(
                    model=self.config.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=self.tools,
                    messages=self.messages,
                )

                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens

                if response.stop_reason == "end_turn":
                    break

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                n_tools_in_turn = max(len(tool_use_blocks), 1)
                turn_input = response.usage.input_tokens
                turn_output = response.usage.output_tokens

                tool_results = []
                for block in tool_use_blocks:
                    call_start = time.time()
                    result = await self._execute_tool(block.name, block.input)
                    call_ms = int((time.time() - call_start) * 1000)

                    result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                    is_error = "error" in result if isinstance(result, dict) else False

                    self.tool_call_log.append(ToolCallRecord(
                        name=block.name,
                        input_tokens=turn_input // n_tools_in_turn,
                        output_tokens=turn_output // n_tools_in_turn,
                        latency_ms=call_ms,
                        response_bytes=len(result_str.encode()),
                        success=not is_error,
                        error=result.get("error") if is_error else None,
                    ))

                    if is_error:
                        self.errors.append(result.get("error", "unknown"))
                        self._last_failed_tool = block.name
                    elif self._last_failed_tool == block.name:
                        self.error_recoveries += 1
                        self._last_failed_tool = None

                    if block.name == "brow_session_new" and not is_error:
                        self._brow_session_id = result.get("output", "").strip()

                    if block.name == "submit_answer":
                        final_output = result.get("answer", {})
                        self.messages.append({"role": "assistant", "content": response.content})
                        return final_output

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

                self.messages.append({"role": "assistant", "content": response.content})
                if tool_results:
                    self.messages.append({"role": "user", "content": tool_results})

        finally:
            if self._mcp_client:
                await self._mcp_client.stop()
            if self.backend == "brow" and self._brow_session_id:
                try:
                    import subprocess
                    subprocess.run(["brow", "session", "delete", self._brow_session_id],
                                   capture_output=True, timeout=10)
                except Exception:
                    pass

        return final_output

    async def _execute_tool(self, name, params):
        if name == "submit_answer":
            return execute_submit_answer(params)
        if self.backend == "brow":
            return execute_brow_tool(name, params)
        return await execute_mcp_tool(self._mcp_client, name, params)
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_agent.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/harness/agent.py benchmarks/tests/test_agent.py
git commit -m "feat(bench): add agent harness with Claude API conversation loop"
```

---

### Task 6: Runner (Orchestration)

**Files:**
- Create: `benchmarks/harness/runner.py`
- Create: `benchmarks/tests/test_runner.py`

- [ ] **Step 1: Write failing test for task loading and run plan**

```python
# benchmarks/tests/test_runner.py
import yaml
from pathlib import Path
from benchmarks.harness.runner import load_task, build_run_plan

def test_load_task(tmp_path):
    task_yaml = {
        "id": "test-task",
        "name": "Test Task",
        "category": "practical",
        "url": "http://localhost/test",
        "requires_fixture": True,
        "description": "Do a test thing",
        "max_steps": 10,
        "timeout_seconds": 60,
        "success_criteria": [{"type": "no_errors"}],
        "tags": ["test"],
    }
    p = tmp_path / "test-task.yaml"
    p.write_text(yaml.dump(task_yaml))
    task = load_task(p)
    assert task["id"] == "test-task"
    assert task["max_steps"] == 10

def test_build_run_plan():
    tasks = [{"id": "t1"}, {"id": "t2"}]
    plan = build_run_plan(tasks, backends=["brow", "mcp-playwright"], runs=2)
    assert len(plan) == 8  # 2 tasks * 2 backends * 2 runs
    backends_per_task = [p["backend"] for p in plan if p["task"]["id"] == "t1"]
    assert "brow" in backends_per_task
    assert "mcp-playwright" in backends_per_task
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement runner.py**

```python
# benchmarks/harness/runner.py
import asyncio
import json
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from benchmarks.harness.agent import AgentLoop
from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.judge import evaluate_all
from benchmarks.harness.metrics import RunResult
from benchmarks.harness.server import FixtureServer
from benchmarks.harness.tools_brow import execute_brow_tool

def load_task(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def load_all_tasks(tasks_dir: Path, task_ids=None, include_live=False) -> list[dict]:
    tasks = []
    for p in sorted(tasks_dir.glob("*.yaml")):
        task = load_task(p)
        if task_ids and task["id"] not in task_ids:
            continue
        if not include_live and not task.get("requires_fixture", True):
            continue
        tasks.append(task)
    return tasks

def build_run_plan(tasks, backends, runs):
    plan = []
    for run_idx in range(runs):
        shuffled = list(tasks)
        random.shuffle(shuffled)
        for task in shuffled:
            for backend in backends:
                plan.append({"task": task, "backend": backend, "run_idx": run_idx})
    interleaved = []
    for run_idx in range(runs):
        run_items = [p for p in plan if p["run_idx"] == run_idx]
        by_task = {}
        for item in run_items:
            by_task.setdefault(item["task"]["id"], []).append(item)
        for items in by_task.values():
            random.shuffle(items)
            interleaved.extend(items)
    return interleaved

async def _get_browser_state(agent):
    state = {"url": ""}
    if agent.backend == "brow" and agent._brow_session_id:
        try:
            result = execute_brow_tool("brow_url", {"session": agent._brow_session_id})
            state["url"] = result.get("output", "").strip()
        except Exception:
            pass
    return state

def _get_brow_version():
    try:
        import subprocess
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

async def run_single(task, backend, config: BenchmarkConfig, fixture_url=None):
    url = task.get("url", "")
    if task.get("requires_fixture") and fixture_url:
        url = url.replace("FIXTURE_URL", fixture_url)
        task = {**task, "url": url, "description": task["description"].replace("FIXTURE_URL", fixture_url)}

    agent = AgentLoop(config=config, backend=backend, task_description=task["description"])
    start = time.time()
    final_output = await agent.run(
        max_steps=task.get("max_steps", 15),
        timeout_seconds=task.get("timeout_seconds", 120),
    )
    wall_clock_ms = int((time.time() - start) * 1000)

    browser_state = await _get_browser_state(agent)
    success = evaluate_all(
        task.get("success_criteria", []),
        final_output,
        browser_state,
        errors=agent.errors,
    )

    return RunResult(
        task_id=task["id"],
        backend=backend,
        model=config.model,
        success=success,
        total_input_tokens=agent.total_input_tokens,
        total_output_tokens=agent.total_output_tokens,
        tool_calls=len(agent.tool_call_log),
        tool_call_log=agent.tool_call_log,
        wall_clock_ms=wall_clock_ms,
        errors=agent.errors,
        error_recoveries=agent.error_recoveries,
        final_output=final_output,
        run_id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        brow_version=_get_brow_version(),
        conversation_turns=agent.conversation_turns,
    )

async def run_benchmark(config: BenchmarkConfig, task_ids=None):
    tasks = load_all_tasks(config.tasks_dir, task_ids, config.include_live)
    if not tasks:
        print("No tasks found")
        return []

    needs_fixture = any(t.get("requires_fixture") for t in tasks)
    server = None
    fixture_url = None

    if needs_fixture:
        server = FixtureServer()
        await server.start()
        fixture_url = server.base_url

    plan = build_run_plan(tasks, config.backends, config.runs)

    warmup_plan = build_run_plan(tasks[:1], config.backends, config.warmup)
    for item in warmup_plan:
        print(f"  warmup: {item['task']['id']} / {item['backend']}")
        await run_single(item["task"], item["backend"], config, fixture_url)

    results = []
    total = len(plan)
    for i, item in enumerate(plan, 1):
        print(f"  [{i}/{total}] {item['task']['id']} / {item['backend']} (run {item['run_idx'] + 1})")
        result = await run_single(item["task"], item["backend"], config, fixture_url)
        results.append(result)

    if server:
        await server.stop()

    return results
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_runner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/harness/runner.py benchmarks/tests/test_runner.py
git commit -m "feat(bench): add runner with task loading, run planning, and orchestration"
```

---

### Task 7: Reporter (Markdown + JSON Output)

**Files:**
- Create: `benchmarks/harness/reporter.py`
- Create: `benchmarks/tests/test_reporter.py`

- [ ] **Step 1: Write failing test**

```python
# benchmarks/tests/test_reporter.py
from benchmarks.harness.reporter import generate_report, save_results_json
from benchmarks.harness.metrics import RunResult
from benchmarks.harness.config import BenchmarkConfig

def _make_result(task_id, backend, tokens_in, tokens_out, calls, success, wall_ms):
    return RunResult(
        task_id=task_id, backend=backend, model="claude-sonnet-4-20250514",
        success=success, total_input_tokens=tokens_in, total_output_tokens=tokens_out,
        tool_calls=calls, tool_call_log=[], wall_clock_ms=wall_ms,
        errors=[], error_recoveries=0, final_output={},
        run_id="r1", timestamp="t", brow_version="v", conversation_turns=calls,
    )

def test_generate_report():
    results = [
        _make_result("t1", "brow", 1000, 500, 5, True, 3000),
        _make_result("t1", "brow", 1200, 600, 6, True, 3500),
        _make_result("t1", "mcp-playwright", 3000, 1500, 12, True, 8000),
        _make_result("t1", "mcp-playwright", 3200, 1600, 14, False, 9000),
    ]
    cfg = BenchmarkConfig()
    report = generate_report(results, cfg)
    assert "Summary" in report
    assert "brow" in report
    assert "mcp-playwright" in report or "MCP" in report

def test_save_results_json(tmp_path):
    results = [_make_result("t1", "brow", 1000, 500, 5, True, 3000)]
    save_results_json(results, tmp_path / "results.json")
    assert (tmp_path / "results.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_reporter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement reporter.py**

```python
# benchmarks/harness/reporter.py
import json
from dataclasses import asdict
from pathlib import Path

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.metrics import RunResult, aggregate_results

def generate_report(results: list[RunResult], config: BenchmarkConfig) -> str:
    lines = [f"## Benchmark Results ({config.model}, {config.runs} runs per task)\n"]

    by_backend = {}
    for r in results:
        by_backend.setdefault(r.backend, []).append(r)

    lines.append("### Summary")
    lines.append("| Metric | " + " | ".join(by_backend.keys()) + " | Delta |")
    lines.append("|--------|" + "|".join(["--------"] * len(by_backend)) + "|-------|")

    aggs = {b: aggregate_results(rs) for b, rs in by_backend.items()}
    backends = list(aggs.keys())

    metrics = [
        ("Avg tokens/task", "mean_tokens", "stddev_tokens", "{:.0f}"),
        ("Avg tool calls/task", "mean_tool_calls", "stddev_tool_calls", "{:.1f}"),
        ("Success rate", "success_rate", None, "{:.0%}"),
        ("Avg wall-clock (s)", "mean_wall_clock_ms", "stddev_wall_clock_ms", None),
    ]

    for label, key, std_key, fmt in metrics:
        vals = []
        for b in backends:
            v = aggs[b][key]
            if key == "mean_wall_clock_ms":
                v_display = f"{v / 1000:.1f}"
                if std_key:
                    v_display += f"+/-{aggs[b][std_key] / 1000:.1f}"
            elif std_key:
                v_display = fmt.format(v) + f"+/-{fmt.format(aggs[b][std_key])}"
            else:
                v_display = fmt.format(v)
            vals.append(v_display)

        delta = ""
        if len(backends) == 2:
            v0, v1 = aggs[backends[0]][key], aggs[backends[1]][key]
            if v1 != 0:
                pct = (v0 - v1) / v1 * 100
                delta = f"{pct:+.0f}%"

        lines.append(f"| {label} | " + " | ".join(vals) + f" | {delta} |")

    cost_line_vals = []
    for b in backends:
        a = aggs[b]
        cost = config.estimate_cost(int(a["mean_input_tokens"]), int(a["mean_output_tokens"]))
        cost_line_vals.append(f"${cost:.4f}")
    cost_delta = ""
    if len(backends) == 2 and float(cost_line_vals[1].strip("$")) != 0:
        c0, c1 = float(cost_line_vals[0].strip("$")), float(cost_line_vals[1].strip("$"))
        cost_delta = f"{(c0 - c1) / c1 * 100:+.0f}%"
    lines.append(f"| Est. cost/task | " + " | ".join(cost_line_vals) + f" | {cost_delta} |")

    lines.append("\n### Per-Task Breakdown")
    lines.append("| Task | Backend | Tokens | Calls | Success | Time (s) |")
    lines.append("|------|---------|--------|-------|---------|----------|")

    by_task_backend = {}
    for r in results:
        by_task_backend.setdefault((r.task_id, r.backend), []).append(r)

    for (task_id, backend), rs in sorted(by_task_backend.items()):
        a = aggregate_results(rs)
        n = a["n"]
        successes = sum(1 for r in rs if r.success)
        tokens = f"{a['mean_tokens']:.0f}+/-{a['stddev_tokens']:.0f}"
        calls = f"{a['mean_tool_calls']:.1f}+/-{a['stddev_tool_calls']:.1f}"
        time_s = f"{a['mean_wall_clock_ms']/1000:.1f}+/-{a['stddev_wall_clock_ms']/1000:.1f}"
        lines.append(f"| {task_id} | {backend} | {tokens} | {calls} | {successes}/{n} | {time_s} |")

    return "\n".join(lines) + "\n"


def save_results_json(results: list[RunResult], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for r in results:
        d = {
            "task_id": r.task_id, "backend": r.backend, "model": r.model,
            "success": r.success, "total_input_tokens": r.total_input_tokens,
            "total_output_tokens": r.total_output_tokens, "tool_calls": r.tool_calls,
            "wall_clock_ms": r.wall_clock_ms, "errors": r.errors,
            "error_recoveries": r.error_recoveries, "run_id": r.run_id,
            "timestamp": r.timestamp, "brow_version": r.brow_version,
            "conversation_turns": r.conversation_turns,
            "tool_call_log": [
                {"name": t.name, "input_tokens": t.input_tokens, "output_tokens": t.output_tokens,
                 "latency_ms": t.latency_ms, "response_bytes": t.response_bytes,
                 "success": t.success, "error": t.error}
                for t in r.tool_call_log
            ],
        }
        data.append(d)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def save_report(results: list[RunResult], config: BenchmarkConfig):
    config.output_dir.mkdir(parents=True, exist_ok=True)
    report = generate_report(results, config)
    (config.output_dir / "report.md").write_text(report)
    save_results_json(results, config.output_dir / "results.json")
    print(f"Report saved to {config.output_dir / 'report.md'}")
    print(f"Raw data saved to {config.output_dir / 'results.json'}")
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/test_reporter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/harness/reporter.py benchmarks/tests/test_reporter.py
git commit -m "feat(bench): add reporter for markdown tables and JSON output"
```

---

### Task 8: CLI Entry Point

**Files:**
- Create: `benchmarks/run.py`

- [ ] **Step 1: Implement run.py**

```python
# benchmarks/run.py
import argparse
import asyncio
import sys

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.runner import run_benchmark
from benchmarks.harness.reporter import save_report

def main():
    parser = argparse.ArgumentParser(description="brow vs MCP Playwright benchmark")
    parser.add_argument("--backend", default="all", choices=["brow", "mcp-playwright", "all"])
    parser.add_argument("--tasks", default="all", help="Task IDs (comma-separated) or 'all'")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    parser.add_argument("--output", default=None)
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()

    if args.backend == "all":
        backends = ["brow", "mcp-playwright"]
    else:
        backends = [args.backend]

    task_ids = None if args.tasks == "all" else args.tasks.split(",")

    config = BenchmarkConfig(
        model=args.model,
        runs=args.runs,
        warmup=args.warmup,
        backends=backends,
        include_live=args.include_live,
    )
    if args.output:
        from pathlib import Path
        config.output_dir = Path(args.output)

    if not config.api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    print(f"Running benchmark: {config.model}, {config.runs} runs, backends: {backends}")
    results = asyncio.run(run_benchmark(config, task_ids))

    if results:
        save_report(results, config)
    else:
        print("No results collected")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it parses args**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m benchmarks.run --help`
Expected: Shows help text with all arguments

- [ ] **Step 3: Commit**

```bash
git add benchmarks/run.py
git commit -m "feat(bench): add CLI entry point for running benchmarks"
```

---

### Task 9: Task YAML Definitions

**Files:**
- Create: `benchmarks/tasks/search-extract.yaml`
- Create: `benchmarks/tasks/form-fill.yaml`
- Create: `benchmarks/tasks/multi-page-nav.yaml`
- Create: `benchmarks/tasks/login-auth.yaml`
- Create: `benchmarks/tasks/dynamic-content.yaml`
- Create: `benchmarks/tasks/ecommerce-search.yaml`
- Create: `benchmarks/tasks/info-lookup.yaml`
- Create: `benchmarks/tasks/large-snapshot.yaml`
- Create: `benchmarks/tasks/error-recovery.yaml`
- Create: `benchmarks/tasks/rapid-multi-step.yaml`

- [ ] **Step 1: Create all 10 task YAML files**

```yaml
# benchmarks/tasks/search-extract.yaml
id: search-extract
name: "Search and Extract Results"
category: practical
url: "FIXTURE_URL/static/search.html"
requires_fixture: true
description: "Navigate to FIXTURE_URL/static/search.html and extract the top 5 search results. For each result, extract the title text and the href URL. Return as a list of objects with 'title' and 'url' fields."
max_steps: 10
timeout_seconds: 60
success_criteria:
  - type: structured_output
    min_fields: ["title", "url"]
    min_results: 5
tags: [search, extraction, single-page]
```

```yaml
# benchmarks/tasks/form-fill.yaml
id: form-fill
name: "Fill and Submit Form"
category: practical
url: "FIXTURE_URL/static/form.html"
requires_fixture: true
description: "Navigate to FIXTURE_URL/static/form.html. Fill the form: name='John Doe', email='john@example.com', select subject='Support', message='Need help with account'. Submit the form. Return the confirmation message text."
max_steps: 15
timeout_seconds: 90
success_criteria:
  - type: structured_output
    min_fields: ["confirmation"]
    min_results: 1
tags: [form, interaction]
```

```yaml
# benchmarks/tasks/multi-page-nav.yaml
id: multi-page-nav
name: "Multi-Page Navigation"
category: practical
url: "FIXTURE_URL/static/multipage/page1.html"
requires_fixture: true
description: "Starting at FIXTURE_URL/static/multipage/page1.html, visit all 3 pages (About, Team, Contact). Extract: founded year from page 1, team member count from page 2, email from page 3. Return as object with fields 'founded', 'team_size', 'email'."
max_steps: 20
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["founded", "team_size", "email"]
    min_results: 1
tags: [navigation, multi-page, extraction]
```

```yaml
# benchmarks/tasks/login-auth.yaml
id: login-auth
name: "Login and Authenticated Action"
category: practical
url: "FIXTURE_URL/login"
requires_fixture: true
description: "Navigate to FIXTURE_URL/login. Submit the login form with username='admin', password='password123'. After login, navigate to FIXTURE_URL/dashboard. Extract the username and role from the dashboard. Return as object with 'username' and 'role' fields."
max_steps: 20
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["username", "role"]
    min_results: 1
tags: [auth, login, session]
```

```yaml
# benchmarks/tasks/dynamic-content.yaml
id: dynamic-content
name: "Dynamic Content Extraction"
category: practical
url: "FIXTURE_URL/dynamic"
requires_fixture: true
description: "Navigate to FIXTURE_URL/dynamic. Wait for the dynamic content to load (it appears after ~2 seconds, replacing the 'Loading...' text). Extract all items with their name and value. Return as list of objects with 'name' and 'value' fields."
max_steps: 12
timeout_seconds: 60
success_criteria:
  - type: structured_output
    min_fields: ["name", "value"]
    min_results: 3
tags: [dynamic, wait, extraction]
```

```yaml
# benchmarks/tasks/ecommerce-search.yaml
id: ecommerce-search
name: "E-commerce Product Search"
category: academic
url: "FIXTURE_URL/static/catalog.html"
requires_fixture: true
description: "Navigate to FIXTURE_URL/static/catalog.html. Find the laptop with the highest rating. Return its name, price, and rating as an object with fields 'name', 'price', 'rating'."
max_steps: 12
timeout_seconds: 60
success_criteria:
  - type: structured_output
    min_fields: ["name", "price", "rating"]
    min_results: 1
tags: [ecommerce, search, extraction]
```

```yaml
# benchmarks/tasks/info-lookup.yaml
id: info-lookup
name: "Information Lookup"
category: academic
url: "FIXTURE_URL/static/wiki/index.html"
requires_fixture: true
description: "Navigate to FIXTURE_URL/static/wiki/index.html. Find the topic 'Photosynthesis' and click through to its page. Extract the discovery year and discoverer. Return as object with fields 'discovery_year' and 'discoverer'."
max_steps: 15
timeout_seconds: 90
success_criteria:
  - type: structured_output
    min_fields: ["discovery_year", "discoverer"]
    min_results: 1
tags: [wiki, lookup, multi-page]
```

```yaml
# benchmarks/tasks/large-snapshot.yaml
id: large-snapshot
name: "Large Page Snapshot"
category: stress
url: "FIXTURE_URL/large"
requires_fixture: true
description: "Navigate to FIXTURE_URL/large. The page has 550 items. Extract the value of item 100 and item 500. Return as object with fields 'item_100_value' and 'item_500_value'."
max_steps: 10
timeout_seconds: 90
success_criteria:
  - type: structured_output
    min_fields: ["item_100_value", "item_500_value"]
    min_results: 1
tags: [stress, large-page, snapshot]
```

```yaml
# benchmarks/tasks/error-recovery.yaml
id: error-recovery
name: "Error Recovery"
category: stress
url: "FIXTURE_URL/flaky"
requires_fixture: true
description: "Navigate to FIXTURE_URL/flaky. The page randomly shows or hides an element with id 'flaky-element'. Keep refreshing the page (navigate again) until you find the element, then extract its text. Return as object with field 'text'."
max_steps: 20
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["text"]
    min_results: 1
tags: [stress, error-recovery, retry]
```

```yaml
# benchmarks/tasks/rapid-multi-step.yaml
id: rapid-multi-step
name: "Rapid Multi-Step Wizard"
category: stress
url: "FIXTURE_URL/static/steps.html"
requires_fixture: true
description: "Navigate to FIXTURE_URL/static/steps.html. Complete the 4-step registration wizard: Step 1 - fill first-name='Jane', last-name='Smith', click Next. Step 2 - fill phone='555-1234', city='New York', click Next. Step 3 - select color='Blue', check newsletter checkbox, click Next. Step 4 - click Submit. Extract the confirmation message from step 5. Return as object with field 'confirmation'."
max_steps: 25
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["confirmation"]
    min_results: 1
tags: [stress, multi-step, interaction]
```

- [ ] **Step 2: Verify tasks load**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -c "from benchmarks.harness.runner import load_all_tasks; from pathlib import Path; tasks = load_all_tasks(Path('benchmarks/tasks')); print(f'{len(tasks)} tasks loaded'); [print(f'  {t[\"id\"]}') for t in tasks]"`
Expected: `10 tasks loaded` with all task IDs listed

- [ ] **Step 3: Commit**

```bash
git add benchmarks/tasks/
git commit -m "feat(bench): add 10 benchmark task definitions"
```

---

### Task 10: Integration Test and Final Wiring

**Files:**
- Create: `benchmarks/tests/test_integration.py`

- [ ] **Step 1: Write integration test (mocked Claude API)**

```python
# benchmarks/tests/test_integration.py
from unittest.mock import patch, MagicMock
from pathlib import Path

from benchmarks.harness.config import BenchmarkConfig
from benchmarks.harness.runner import load_all_tasks, build_run_plan
from benchmarks.harness.reporter import generate_report
from benchmarks.harness.metrics import RunResult

def test_full_pipeline_mocked():
    tasks_dir = Path(__file__).parent.parent / "tasks"
    tasks = load_all_tasks(tasks_dir)
    assert len(tasks) == 10

    plan = build_run_plan(tasks, ["brow", "mcp-playwright"], runs=1)
    assert len(plan) == 20

    results = []
    for item in plan:
        results.append(RunResult(
            task_id=item["task"]["id"], backend=item["backend"],
            model="claude-sonnet-4-20250514", success=True,
            total_input_tokens=2000, total_output_tokens=800,
            tool_calls=6, tool_call_log=[], wall_clock_ms=5000,
            errors=[], error_recoveries=0, final_output={},
            run_id="test", timestamp="t", brow_version="v",
            conversation_turns=6,
        ))

    cfg = BenchmarkConfig(runs=1)
    report = generate_report(results, cfg)
    assert "Summary" in report
    assert "brow" in report
    assert "search-extract" in report

def test_tasks_all_have_required_fields():
    tasks_dir = Path(__file__).parent.parent / "tasks"
    tasks = load_all_tasks(tasks_dir)
    required = ["id", "name", "category", "description", "max_steps", "timeout_seconds", "success_criteria"]
    for task in tasks:
        for field in required:
            assert field in task, f"Task {task.get('id', 'unknown')} missing field: {field}"
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m pytest benchmarks/tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Run CLI help to verify wiring**

Run: `cd /Users/danherma/Documents/projects-personal/brow && python -m benchmarks.run --help`
Expected: Help output with all arguments

- [ ] **Step 4: Commit**

```bash
git add benchmarks/tests/test_integration.py
git commit -m "feat(bench): add integration tests and verify full pipeline"
```

- [ ] **Step 5: Create requirements.txt**

```
# benchmarks/requirements.txt
anthropic>=0.40
pyyaml>=6.0
fastapi>=0.104
uvicorn>=0.24
httpx>=0.25
pytest>=7.0
pytest-asyncio>=0.23
```

- [ ] **Step 6: Final commit with all benchmarks**

```bash
git add -A benchmarks/
git commit -m "feat: complete agent benchmark framework (brow vs MCP Playwright)"
```
