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
async def test_eval_timeout_message_is_actionable(client, session_id):
    """A bare 'Eval timed out' sends agents off building batching machinery.

    The timeout is raisable per call, but nothing in the error said so, so the
    reasonable-looking response to a long job was to stage it on window.* and
    drain it a few items per call. The message has to name the knob.
    """
    r = await client.post(f"/eval/{session_id}", json={"code": "await asyncio.sleep(2)", "timeout": 200})
    assert r.status_code == 408
    detail = r.json()["detail"]
    assert "200" in detail, f"should report the limit that was hit: {detail}"
    assert "timeout" in detail.lower()
    assert "--timeout" in detail, f"should name the flag that raises it: {detail}"


@pytest.mark.asyncio
async def test_eval_honours_raised_timeout(client, session_id):
    """The escape hatch the message points at has to actually work."""
    r = await client.post(f"/eval/{session_id}", json={"code": "await asyncio.sleep(1)\nresult = 'done'", "timeout": 15000})
    assert r.status_code == 200
    assert r.json()["result"] == "done"


@pytest.mark.asyncio
async def test_eval_partial_stdout_survives_timeout(client, session_id):
    """Output printed before a timeout must not be thrown away.

    Long eval jobs print progress as they go. Discarding stdout on timeout means
    a job that did 80% of the work reports nothing, so there is no way to know
    where to resume, which forces a full re-run.
    """
    code = "print('did-item-1')\nprint('did-item-2')\nawait asyncio.sleep(5)"
    r = await client.post(f"/eval/{session_id}", json={"code": code, "timeout": 700})
    assert r.status_code == 408
    detail = r.json()["detail"]
    assert "did-item-1" in detail, f"partial progress was discarded: {detail}"
    assert "did-item-2" in detail


@pytest.mark.asyncio
async def test_eval_coroutine_hint(client, session_id):
    await client.post(f"/browser/{session_id}/navigate", json={"url": "data:text/html,<h1>Hi</h1>"})
    r = await client.post(
        f"/eval/{session_id}", json={"code": "el = page.query_selector('h1')\nresult = el.inner_text()"}
    )
    assert r.status_code == 400
    assert "await" in r.json()["detail"]
