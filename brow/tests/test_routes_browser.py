import pytest
from httpx import AsyncClient, ASGITransport
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
    assert r.json()["ok"] == True

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
    mgr = None
    async with create_app().router.lifespan_context(create_app()) as state:
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
    heading_line = [l for l in tree.strip().split("\n") if "Title" in l][0]
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
async def test_select(client, session_id):
    html = "data:text/html,<body><select id='sel'><option value='a'>A</option><option value='b'>B</option></select></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/select", json={"selector": "#sel", "value": "b"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

@pytest.mark.asyncio
async def test_select_by_ref(client, session_id):
    html = "data:text/html,<body><select id='sel'><option value='a'>A</option><option value='b'>B</option></select></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.get(f"/browser/{session_id}/snapshot")
    r = await client.post(f"/browser/{session_id}/select", json={"ref": 3, "value": "b"})
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
        json={"url": "data:text/html,<body><h1>Hello</h1><button>Click</button></body>"}
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
    lines = [l for l in tree.strip().split("\n") if "Home" in l or "FAQ" in l]
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_session_not_found(client):
    r = await client.get("/browser/999/url")
    assert r.status_code == 404
