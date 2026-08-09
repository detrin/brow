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
async def test_switch_page_retargets_subsequent_commands(client, session_id):
    """switch must change where LATER commands go, not just report an index.

    This asserted only the echoed response before, which is why the switch was a
    no-op for a long time: Session.page returned pages[-1] ("last opened"), so
    every command kept hitting the newest tab no matter what was switched to.
    An agent driving two tabs had to write page.context.pages[i] inside eval to
    work around it.
    """
    await client.post(f"/pages/{session_id}/new", json={"url": "data:text/html,<title>zero</title>"})
    await client.post(f"/pages/{session_id}/new", json={"url": "data:text/html,<title>one</title>"})
    pages = (await client.get(f"/pages/{session_id}")).json()["pages"]
    assert len(pages) >= 3

    await client.post(f"/pages/{session_id}/switch", json={"index": 1})
    r = await client.get(f"/browser/{session_id}/url")
    assert r.status_code == 200
    assert r.json()["url"] == pages[1]["url"], "url command ignored the switch"

    r = await client.post(f"/eval/{session_id}", json={"code": "result = page.url"})
    assert r.json()["result"] == pages[1]["url"], "eval ignored the switch"


@pytest.mark.asyncio
async def test_active_page_survives_new_tab(client, session_id):
    """Opening a tab should not silently steal the target from the active one.

    A background tab opened by a click (OAuth popup, target=_blank) used to
    become the implicit target of every following command.
    """
    await client.post(f"/pages/{session_id}/switch", json={"index": 0})
    before = (await client.get(f"/browser/{session_id}/url")).json()["url"]
    await client.post(f"/pages/{session_id}/new", json={"url": "data:text/html,<title>popup</title>"})
    after = (await client.get(f"/browser/{session_id}/url")).json()["url"]
    assert after == before, "a newly opened tab hijacked the active page"


@pytest.mark.asyncio
async def test_close_active_page_falls_back(client, session_id):
    """Closing the active tab must leave a valid target, not a dead handle."""
    await client.post(f"/pages/{session_id}/new", json={"url": "data:text/html,<title>second</title>"})
    await client.post(f"/pages/{session_id}/switch", json={"index": 1})
    await client.post(f"/pages/{session_id}/close", params={"index": 1})
    r = await client.get(f"/browser/{session_id}/url")
    assert r.status_code == 200, f"no usable page after closing the active one: {r.text}"


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
