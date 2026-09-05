import re

import pytest
from httpx import ASGITransport, AsyncClient

from brow.daemon import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with app.router.lifespan_context(app) as _:
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
    assert "url" in r.json()


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


@pytest.mark.asyncio
async def test_wait(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Test</h1>"})
    r = await client.post(f"/browser/{session_id}/wait", json={"load": True})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_type(client, session_id):
    html = "data:text/html,<input id='inp' type='text'/>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.post(f"/browser/{session_id}/click", json={"selector": "#inp"})
    r = await client.post(f"/browser/{session_id}/type", json={"text": "test"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_key(client, session_id):
    html = "data:text/html,<input id='inp' type='text'/>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.post(f"/browser/{session_id}/click", json={"selector": "#inp"})
    r = await client.post(f"/browser/{session_id}/key", json={"key": "Enter"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_hover(client, session_id):
    html = "data:text/html,<button id='btn'>Hover</button>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/hover", json={"selector": "#btn"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_scroll(client, session_id):
    html = "data:text/html,<div style='height:2000px'>Content</div>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/scroll", json={"pixels": 100})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_no_active_page(client):
    r = await client.post("/sessions", json={"profile": "nopage", "headless": True})
    sid = r.json()["id"]
    await client.delete(f"/sessions/{sid}")
    r2 = await client.post("/sessions", json={"profile": "nopage2", "headless": True})
    sid2 = r2.json()["id"]
    async with create_app().router.lifespan_context(create_app()):
        pass
    r = await client.get(f"/browser/{sid2}/url")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_snapshot_has_refs(client, session_id):
    html = "data:text/html,<body><a href='/'>Home</a><h1>Title</h1><button>Click</button></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert "[1]" in tree
    assert "[2]" in tree
    heading_line = [line for line in tree.strip().split("\n") if "Title" in line][0]
    assert "[" not in heading_line


@pytest.mark.asyncio
async def test_click_by_ref(client, session_id):
    html = "data:text/html,<body><button id='btn' onclick='document.title=\"clicked\"'>Click</button></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.get(f"/browser/{session_id}/snapshot")  # inject refs
    r = await client.post(f"/browser/{session_id}/click", json={"ref": 1})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_fill_by_ref(client, session_id):
    html = "data:text/html,<body><input id='inp' type='text'/></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.get(f"/browser/{session_id}/snapshot")  # inject refs
    r = await client.post(f"/browser/{session_id}/fill", json={"ref": 1, "value": "hello"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_click_bracket_ref_as_selector(client, session_id):
    html = "data:text/html,<body><button id='btn' onclick='document.title=\"clicked\"'>Click</button></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.get(f"/browser/{session_id}/snapshot")
    r = await client.post(f"/browser/{session_id}/click", json={"selector": "[1]"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_navigate_wait_networkidle(client, session_id):
    r = await client.post(
        f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hi</h1>", "wait": "networkidle"}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_select(client, session_id):
    html = (
        "data:text/html,<body><select id='sel'><option value='a'>A</option><option value='b'>B</option></select></body>"
    )
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/select", json={"selector": "#sel", "value": "b"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_select_by_ref(client, session_id):
    html = (
        "data:text/html,<body><select id='sel'><option value='a'>A</option><option value='b'>B</option></select></body>"
    )
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    snap = await client.get(f"/browser/{session_id}/snapshot")
    # Read the ref off the snapshot rather than hardcoding it: refs are numbered
    # in reading order, so a hardcoded number silently retargets if the walk changes.
    ref = int(re.search(r"\[(\d+)\] select", snap.json()["tree"]).group(1))
    r = await client.post(f"/browser/{session_id}/select", json={"ref": ref, "value": "b"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_click_returns_snapshot(client, session_id):
    html = "data:text/html,<body><a href='data:text/html,<h1>Page2</h1>'>Go</a></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/click", json={"selector": "a"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "snapshot" in body
    assert "Page2" in body["snapshot"]


@pytest.mark.asyncio
async def test_fill_returns_snapshot(client, session_id):
    html = "data:text/html,<body><input id='inp' type='text'/><p>Label</p></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/fill", json={"selector": "#inp", "value": "test"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "snapshot" in body


@pytest.mark.asyncio
async def test_navigate_returns_snapshot(client, session_id):
    r = await client.post(
        f"/browser/{session_id}/navigate",
        json={"url": "data:text/html,<body><h1>Hello</h1><button>Click</button></body>"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "snapshot" in body
    assert "Hello" in body["snapshot"]
    assert "[1]" in body["snapshot"]


@pytest.mark.asyncio
async def test_snapshot_table_compact(client, session_id):
    html = """data:text/html,<body><table>
        <thead><tr><th>Name</th><th>Price</th></tr></thead>
        <tbody>
            <tr><td>Widget A</td><td>$10</td></tr>
            <tr><td>Widget B</td><td>$20</td></tr>
            <tr><td>Widget C</td><td>$30</td></tr>
        </tbody>
    </table></body>"""
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert "| Name | Price |" in tree
    assert "Widget A" in tree
    assert "Widget C" in tree


@pytest.mark.asyncio
async def test_snapshot_list_compression(client, session_id):
    html = """data:text/html,<body><nav>
        <a href="/home">Home</a>
        <a href="/about">About</a>
        <a href="/products">Products</a>
        <a href="/blog">Blog</a>
        <a href="/contact">Contact</a>
        <a href="/help">Help</a>
        <a href="/faq">FAQ</a>
    </nav></body>"""
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert "[1]" in tree
    assert "[7]" in tree
    lines = [line for line in tree.strip().split("\n") if "Home" in line or "FAQ" in line]
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_adaptive_cap_simple_page(client, session_id):
    """Simple page with few interactive elements gets lower node cap (200)."""
    html = "data:text/html,<body><h1>Title</h1><p>Paragraph</p><a href='/'>Link</a></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    assert "Title" in r.json()["tree"]


@pytest.mark.asyncio
async def test_adaptive_cap_many_interactive(client, session_id):
    """Page with many interactive elements gets higher cap and prioritizes them."""
    # Use distinct elements to avoid repetition-dedup (different classes)
    buttons = "".join(f'<button class="b{i}">Btn {i}</button>' for i in range(60))
    paragraphs = "".join(f"<p>Filler paragraph {i}</p>" for i in range(200))
    html = f"data:text/html,<body>{buttons}{paragraphs}</body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    # All 60 buttons should have refs (interactive elements prioritized)
    assert "[60]" in tree


@pytest.mark.asyncio
async def test_session_not_found(client):
    r = await client.get("/browser/999/url")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_fetch_reports_status_for_empty_error_body(client, session_id, monkeypatch):
    """An auth failure must be visible, not silent.

    The daemon has always returned the status; the CLI printed only the body. A
    401 with an empty body therefore printed nothing at all, which is
    indistinguishable from success-with-no-content and sends you guessing at
    headers, cookies and origins instead of reading the code.
    """
    import httpx as _httpx

    def handler(request):
        return _httpx.Response(401)

    original_init = _httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = _httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(_httpx.AsyncClient, "__init__", patched_init)

    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>x</h1>"})
    r = await client.post(
        f"/browser/{session_id}/fetch",
        json={"url": "https://example.invalid/status/401", "method": "GET", "no_cookies": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == 401


@pytest.mark.asyncio
async def test_click_until_drains_a_queue(client, session_id):
    """Repeat a click until the work runs out, in ONE call.

    This is the shape of every bulk UI job: act on the visible batch, the list
    refills, act again. Done from the outside it costs a fresh process plus an
    HTTP round trip per iteration (~250ms each) and needs hand-rolled
    loop-guard logic to know when to stop.
    """
    html = """data:text/html,<body>
    <div id=list>item item item item item</div>
    <button id=go onclick="
      var l=document.getElementById('list');
      var w=l.textContent.trim().split(/\\s+/);
      w.pop(); l.textContent=w.join(' ');
    ">Go</button></body>"""
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(
        f"/browser/{session_id}/click-until",
        json={"selector": "#go", "until_gone": "#list:has-text('item')", "max_iterations": 20},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["iterations"] == 5, f"should click exactly until drained: {data}"
    assert data["done"] is True


@pytest.mark.asyncio
async def test_click_until_reports_hitting_the_cap(client, session_id):
    """Stopping early must be loud, so a partial sweep is never read as complete."""
    html = "data:text/html,<body><div id=x>never goes away</div><button id=go>Go</button></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(
        f"/browser/{session_id}/click-until",
        json={"selector": "#go", "until_gone": "#x", "max_iterations": 3},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["done"] is False
    assert data["iterations"] == 3
    assert "max_iterations" in data.get("reason", "")


@pytest.mark.asyncio
async def test_replay_fetch_output_is_usable_as_a_variable_in_later_steps(client, session_id):
    """A captured fetch result must be substitutable into later steps.

    The playbook-writer docs teach `output: name` then `{name}` in a later
    step's url/selector/value. Capturing into the result entry only (not the
    substitution table) makes every documented chaining example silently do
    nothing on the second step.
    """
    html = "data:text/html,<script>window.got=null</script><body></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {
        "base_url": "",
        "steps": [
            {"action": "fetch", "url": 'data:application/json,{"id":"42"}', "output": "item"},
            {"action": "navigate", "url": "data:text/html,<h1>id-{item[id]}</h1>"},
        ],
    }
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert all(x["ok"] for x in results), results
    assert "id-42" in results[1]["url"]


@pytest.mark.asyncio
async def test_replay_wait_step_supports_selector(client, session_id):
    """`wait` must be able to wait for a condition, not just a fixed sleep."""
    html = """data:text/html,<body>
    <script>setTimeout(() => { document.body.innerHTML += '<div id=ready>ok</div>' }, 50)</script>
    </body>"""
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {"steps": [{"action": "wait", "selector": "#ready", "timeout": 2000}]}
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["ok"] is True


@pytest.mark.asyncio
async def test_replay_assert_step_passes_when_condition_holds(client, session_id):
    html = "data:text/html,<body><h1 id=title>Loaded</h1></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {"steps": [{"action": "assert", "selector": "#title", "state": "visible"}]}
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["ok"] is True


@pytest.mark.asyncio
async def test_replay_assert_step_fails_loudly_when_condition_does_not_hold(client, session_id):
    """A playbook must be able to check its own work, not just hope it worked."""
    html = "data:text/html,<body><h1 id=title>Loaded</h1></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {"steps": [{"action": "assert", "selector": "#does-not-exist", "state": "visible", "timeout": 200}]}
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    entry = r.json()["results"][0]
    assert entry["ok"] is False
    assert entry.get("error")


@pytest.mark.asyncio
async def test_replay_stop_on_failure_halts_remaining_steps(client, session_id):
    html = "data:text/html,<body><h1 id=title>Loaded</h1></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {
        "stop_on_failure": True,
        "steps": [
            {"action": "assert", "selector": "#does-not-exist", "timeout": 200},
            {"action": "navigate", "url": "data:text/html,<h1>should not run</h1>"},
        ],
    }
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert len(results) == 1, "later steps must not run once stop_on_failure trips"
    assert results[0]["ok"] is False


@pytest.mark.asyncio
async def test_replay_for_each_repeats_nested_steps_per_item(client, session_id):
    """The recurring shape across real sessions is 'do this for every item in a
    list' via N nearly-identical CLI calls. A playbook must express that as
    one loop, not N steps.
    """
    html = "data:text/html,<body></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {
        "steps": [
            {
                "action": "for_each",
                "var": "n",
                "items": ["a", "b", "c"],
                "steps": [{"action": "navigate", "url": "data:text/html,<h1>item-{n}</h1>"}],
            }
        ],
    }
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert len(results) == 3
    assert [f"item-{c}" in x["url"] for c, x in zip(["a", "b", "c"], results)] == [True, True, True]


@pytest.mark.asyncio
async def test_replay_fetch_step_supports_custom_headers(client, session_id, monkeypatch):
    import httpx as _httpx

    captured = {}
    original_init = _httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        kwargs["transport"] = _httpx.MockTransport(lambda request: _httpx.Response(200, text="ok"))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(_httpx.AsyncClient, "__init__", patched_init)

    html = "data:text/html,<body></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {
        "steps": [
            {
                "action": "fetch",
                "url": "https://example.invalid/thing",
                "auth": "none",
                "headers": {"X-Api-Key": "secret"},
            }
        ],
    }
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["ok"] is True
    assert captured["headers"] == {"X-Api-Key": "secret"}


@pytest.mark.asyncio
async def test_replay_marks_http_error_status_as_failed(client, session_id, monkeypatch):
    """A 500 is not success. Silently marking it ok=True hides real failures."""
    import httpx as _httpx

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = _httpx.MockTransport(lambda request: _httpx.Response(500))
        original_init(self, *args, **kwargs)

    original_init = _httpx.AsyncClient.__init__
    monkeypatch.setattr(_httpx.AsyncClient, "__init__", patched_init)

    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<body></body>"})
    playbook = {"steps": [{"action": "fetch", "url": "https://example.invalid/thing", "auth": "none"}]}
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    entry = r.json()["results"][0]
    assert entry["ok"] is False
    assert entry.get("error")


@pytest.mark.asyncio
async def test_replay_unknown_action_reports_an_error(client, session_id):
    html = "data:text/html,<body></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {"steps": [{"action": "clik", "selector": "#x"}]}
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 422, r.text
    assert "steps[0].action" in r.json()["detail"]
    assert "clik" in r.json()["detail"]


@pytest.mark.asyncio
async def test_replay_stop_on_failure_escapes_nested_for_each(client, session_id):
    """A failure inside a for_each must stop later iterations AND later outer steps."""
    html = "data:text/html,<body></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    playbook = {
        "stop_on_failure": True,
        "steps": [
            {
                "action": "for_each",
                "var": "n",
                "items": ["a", "b", "c"],
                "steps": [
                    {"action": "assert", "selector": "#never-exists", "timeout": 100},
                    {"action": "navigate", "url": "data:text/html,<h1>after-assert-{n}</h1>"},
                ],
            },
            {"action": "navigate", "url": "data:text/html,<h1>should not run</h1>"},
        ],
    }
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert len(results) == 1, f"must stop after the first failed assert, got {results}"
    assert results[0]["ok"] is False


@pytest.mark.asyncio
async def test_replay_top_level_auth_none_is_inherited_by_steps(client, session_id, monkeypatch):
    """Documented `auth: none` at the playbook level must apply when a step omits `auth`."""
    import httpx as _httpx

    used_no_cookies_client = {"called": False}
    original_init = _httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        used_no_cookies_client["called"] = True
        kwargs["transport"] = _httpx.MockTransport(lambda request: _httpx.Response(200, text="ok"))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(_httpx.AsyncClient, "__init__", patched_init)

    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<body></body>"})
    playbook = {"auth": "none", "steps": [{"action": "fetch", "url": "https://example.invalid/thing"}]}
    r = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    assert r.status_code == 200, r.text
    assert used_no_cookies_client["called"] is True
    assert r.json()["results"][0]["ok"] is True


@pytest.mark.asyncio
async def test_password_value_is_omitted_from_fill_snapshot(client, session_id):
    await client.post(
        f"/browser/{session_id}/navigate",
        json={"url": "data:text/html,<label>Password<input id=p type=password></label>"},
    )

    response = await client.post(
        f"/browser/{session_id}/fill",
        json={"selector": "#p", "value": "audit-only-secret"},
    )

    assert response.status_code == 200
    assert "audit-only-secret" not in response.json()["snapshot"]


@pytest.mark.asyncio
async def test_fill_action_log_never_retains_the_value(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<input id=note>"})
    await client.post(
        f"/browser/{session_id}/fill",
        json={"selector": "#note", "value": "private form contents"},
    )

    actions = (await client.get(f"/browser/{session_id}/actions", params={"as_json": True})).json()["actions"]

    assert actions[-1] == {"seq": 2, "action": "fill", "selector": "#note"}


@pytest.mark.asyncio
async def test_replay_fill_action_log_never_retains_the_value(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<input id=token>"})
    playbook = {"steps": [{"action": "fill", "selector": "#token", "value": "token-from-playbook"}]}

    response = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})
    actions = (await client.get(f"/browser/{session_id}/actions", params={"as_json": True})).json()["actions"]

    assert response.status_code == 200
    assert actions[-1] == {"seq": 2, "action": "fill", "selector": "#token"}


@pytest.mark.asyncio
async def test_replay_rejects_unknown_playbook_fields_before_execution(client, session_id):
    response = await client.post(
        f"/browser/{session_id}/replay",
        json={"playbook": {"stepz": [], "steps": []}},
    )

    assert response.status_code == 422
    assert "stepz" in response.json()["detail"]


@pytest.mark.asyncio
async def test_replay_rejects_missing_required_step_fields(client, session_id):
    response = await client.post(
        f"/browser/{session_id}/replay",
        json={"playbook": {"steps": [{"action": "fill", "selector": "#field"}]}},
    )

    assert response.status_code == 422
    assert "steps[0].value" in response.json()["detail"]


@pytest.mark.asyncio
async def test_replay_rejects_unknown_step_fields(client, session_id):
    response = await client.post(
        f"/browser/{session_id}/replay",
        json={"playbook": {"steps": [{"action": "click", "selector": "#save", "selctor": "#typo"}]}},
    )

    assert response.status_code == 422
    assert "steps[0].selctor" in response.json()["detail"]


@pytest.mark.asyncio
async def test_replay_rejects_malformed_nested_steps(client, session_id):
    response = await client.post(
        f"/browser/{session_id}/replay",
        json={"playbook": {"steps": [{"action": "for_each", "var": "item", "items": [], "steps": "not-a-list"}]}},
    )

    assert response.status_code == 422
    assert "steps[0].steps" in response.json()["detail"]


@pytest.mark.asyncio
async def test_replay_reports_undefined_for_each_item_source(client, session_id):
    playbook = {
        "steps": [
            {
                "action": "for_each",
                "var": "item",
                "items": "missing_items",
                "steps": [{"action": "key", "key": "Enter"}],
            }
        ]
    }

    response = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})

    assert response.status_code == 200
    assert response.json()["results"] == [
        {
            "action": "for_each",
            "ok": False,
            "error": "for_each items variable 'missing_items' is not defined",
        }
    ]


@pytest.mark.asyncio
async def test_replay_reports_non_list_for_each_items(client, session_id):
    playbook = {
        "vars": {"items": {"id": 1}},
        "steps": [
            {
                "action": "for_each",
                "var": "item",
                "items": "items",
                "steps": [{"action": "key", "key": "Enter"}],
            }
        ],
    }

    response = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})

    assert response.status_code == 200
    assert response.json()["results"] == [
        {
            "action": "for_each",
            "ok": False,
            "error": "for_each items must resolve to a list, got dict",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "playbook,error_path",
    [
        ({"auth": ["none"], "steps": []}, "auth"),
        ({"steps": [{"action": "wait", "selector": "#ready", "state": ["visible"]}]}, "steps[0].state"),
        ({"steps": [{"action": "fetch", "url": "/api", "auth": ["none"]}]}, "steps[0].auth"),
        ({"steps": [{"action": "fetch", "url": "/api", "expect_status": [200, "201"]}]}, "expect_status"),
        ({"steps": [{"action": "wait", "selector": "#ready", "ms": 10}]}, "steps[0]"),
    ],
)
async def test_replay_rejects_invalid_field_shapes(client, session_id, playbook, error_path):
    response = await client.post(f"/browser/{session_id}/replay", json={"playbook": playbook})

    assert response.status_code == 422
    assert error_path in response.json()["detail"]
