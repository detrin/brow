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


@pytest.mark.asyncio
async def test_eval_text_helper(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hello World</h1>"})
    r = await client.post(f"/eval/{session_id}", json={"code": "result = await text('h1')"})
    assert r.status_code == 200
    assert r.json()["result"] == "Hello World"


@pytest.mark.asyncio
async def test_eval_coroutine_hint(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hi</h1>"})
    r = await client.post(f"/eval/{session_id}", json={"code": "el = page.query_selector('h1')\nresult = el.inner_text()"})
    assert r.status_code == 400
    assert "await" in r.json()["detail"]
