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
    r = await client.post("/states/save", json={"name": "test-state", "session_id": sid})
    assert r.status_code == 200
    r = await client.get("/states")
    assert "test-state" in r.json()["states"]
