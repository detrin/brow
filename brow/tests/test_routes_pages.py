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
async def test_list_pages(client, session_id):
    r = await client.get(f"/pages/{session_id}")
    assert r.status_code == 200
    assert isinstance(r.json()["pages"], list)


@pytest.mark.asyncio
async def test_new_page(client, session_id):
    r = await client.post(f"/pages/{session_id}/new", json={})
    assert r.status_code == 200
    assert "index" in r.json()
    assert "url" in r.json()


@pytest.mark.asyncio
async def test_new_page_with_url(client, session_id):
    r = await client.post(f"/pages/{session_id}/new", json={"url": "https://example.com"})
    assert r.status_code == 200
    assert "example.com" in r.json()["url"]


@pytest.mark.asyncio
async def test_switch_page(client, session_id):
    await client.post(f"/pages/{session_id}/new", json={})
    r = await client.post(f"/pages/{session_id}/switch", json={"index": 0})
    assert r.status_code == 200
    assert r.json()["active"] == 0


@pytest.mark.asyncio
async def test_close_page(client, session_id):
    await client.post(f"/pages/{session_id}/new", json={})
    r = await client.post(f"/pages/{session_id}/close", json={"index": 1})
    assert r.status_code == 200
    assert r.json()["closed"] == 1


@pytest.mark.asyncio
async def test_close_last_page(client, session_id):
    await client.post(f"/pages/{session_id}/new", json={})
    r = await client.post(f"/pages/{session_id}/close")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_page_not_found(client):
    r = await client.get("/pages/999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_invalid_page_index(client, session_id):
    r = await client.post(f"/pages/{session_id}/switch", json={"index": 999})
    assert r.status_code == 400
