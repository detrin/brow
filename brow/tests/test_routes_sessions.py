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
async def test_profile_conflict(client):
    await client.post("/sessions", json={"profile": "dup", "headless": True})
    r = await client.post("/sessions", json={"profile": "dup", "headless": True})
    assert r.status_code == 400
    assert "already in use" in r.json()["detail"]


@pytest.mark.asyncio
async def test_reclaim_profile(client):
    r1 = await client.post("/sessions", json={"profile": "dup", "headless": True})
    old = r1.json()["id"]
    r2 = await client.post("/sessions", json={"profile": "dup", "headless": True, "reclaim": True})
    assert r2.status_code == 200
    sessions = (await client.get("/sessions")).json()
    ids = [s["id"] for s in sessions]
    assert old not in ids
    assert r2.json()["id"] in ids


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
async def test_create_session_browser_missing(client, monkeypatch):
    async def _fail(self, *a, **k):
        raise Exception("Executable doesn't exist at /chromium. Run playwright install")

    monkeypatch.setattr("brow.session.Session.launch", _fail)
    r = await client.post("/sessions", json={"profile": "missing", "headless": True})
    assert r.status_code == 503
    assert "brow setup" in r.json()["detail"]
    assert (await client.get("/sessions")).json() == []


@pytest.mark.asyncio
async def test_create_session_with_url(client):
    r = await client.post(
        "/sessions",
        json={
            "profile": "test-url",
            "headless": True,
            "url": "data:text/html,<body><h1>Hello</h1><button>Click</button></body>",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert "snapshot" in body
    assert "Hello" in body["snapshot"]
    assert "[1]" in body["snapshot"]
