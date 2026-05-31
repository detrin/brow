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
async def test_full_workflow(client):
    r = await client.post("/sessions", json={"profile": "integration", "headless": True})
    assert r.status_code == 200
    sid = r.json()["id"]

    r = await client.post(
        f"/browser/{sid}/navigate",
        json={"url": "data:text/html,<h1>Test</h1><button id='b'>Go</button><input id='i'/>"},
    )
    assert r.status_code == 200

    r = await client.get(f"/browser/{sid}/snapshot")
    assert r.status_code == 200

    r = await client.post(f"/browser/{sid}/click", json={"selector": "#b"})
    assert r.status_code == 200

    r = await client.post(f"/browser/{sid}/fill", json={"selector": "#i", "value": "hello"})
    assert r.status_code == 200

    r = await client.post(f"/browser/{sid}/screenshot", json={})
    assert r.status_code == 200
    assert "path" in r.json()

    r = await client.get(f"/browser/{sid}/html")
    assert r.status_code == 200
    assert "Test" in r.json()["html"]

    r = await client.post(f"/eval/{sid}", json={"code": "result = await page.title()"})
    assert r.status_code == 200

    r = await client.post("/states/save", json={"name": "int-test", "session_id": sid})
    assert r.status_code == 200

    r = await client.post(f"/pages/{sid}/new", json={})
    assert r.status_code == 200

    r = await client.get(f"/pages/{sid}")
    assert r.status_code == 200
    assert len(r.json()["pages"]) >= 2

    r = await client.delete(f"/sessions/{sid}")
    assert r.status_code == 200
