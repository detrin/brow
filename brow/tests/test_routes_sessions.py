import pytest
from httpx import AsyncClient, ASGITransport
from contextlib import asynccontextmanager
from brow.daemon import create_app

@pytest.fixture
async def client():
    app = create_app()
    async with app.router.lifespan_context(app) as _:
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

@pytest.mark.asyncio
async def test_create_session_with_url(client):
    r = await client.post("/sessions", json={
        "profile": "test-url",
        "headless": True,
        "url": "data:text/html,<body><h1>Hello</h1><button>Click</button></body>"
    })
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert "snapshot" in body
    assert "Hello" in body["snapshot"]
    assert "[1]" in body["snapshot"]
