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


@pytest.mark.asyncio
async def test_restore_state_brings_back_local_storage(client):
    """storage_state() captures localStorage under `origins`; restore must
    actually put it back, not just the cookies half of the snapshot — many
    sites keep an auth token in localStorage rather than a cookie.
    """
    r = await client.post("/sessions", json={"profile": "ls-src", "headless": True})
    sid_a = r.json()["id"]
    setup_code = (
        "await context.route('**/*', lambda route: route.fulfill(body='<h1>ok</h1>', content_type='text/html'))\n"
        "await page.goto('https://brow-test.invalid/')\n"
        "await page.evaluate(\"() => localStorage.setItem('token', 'secret-123')\")\n"
    )
    r = await client.post(f"/eval/{sid_a}", json={"code": setup_code})
    assert r.status_code == 200, r.text

    r = await client.post("/states/save", json={"name": "ls-state", "session_id": sid_a})
    assert r.status_code == 200, r.text

    r = await client.post("/sessions", json={"profile": "ls-dst", "headless": True})
    sid_b = r.json()["id"]
    route_code = (
        "await context.route('**/*', lambda route: route.fulfill(body='<h1>ok</h1>', content_type='text/html'))\n"
    )
    await client.post(f"/eval/{sid_b}", json={"code": route_code})

    r = await client.post("/states/restore", json={"name": "ls-state", "session_id": sid_b})
    assert r.status_code == 200, r.text

    check_code = (
        "await page.goto('https://brow-test.invalid/')\n"
        "result = await page.evaluate(\"() => localStorage.getItem('token')\")\n"
    )
    r = await client.post(f"/eval/{sid_b}", json={"code": check_code})
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "secret-123"
