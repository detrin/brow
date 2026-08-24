import httpx
import pytest
import pytest_asyncio
from benchmarks.harness.server import FixtureServer

@pytest_asyncio.fixture
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
        r2 = await client.get(f"{server.base_url}/dashboard")
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
