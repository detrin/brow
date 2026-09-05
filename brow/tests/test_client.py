from unittest.mock import Mock, patch

import pytest

from brow.client import BrowAPIError, BrowClient


@pytest.fixture
def client():
    return BrowClient()


def response(status_code, json=None, text=None):
    resp = Mock()
    resp.status_code = status_code
    resp.is_error = status_code >= 400
    if json is None:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = json
    resp.text = text
    return resp


def transport(client, resp):
    return patch.object(client._client, "request", return_value=resp)


@pytest.mark.asyncio
async def test_post(client):
    with transport(client, response(200, {"id": "1"})) as request:
        assert await client.post("/sessions", json={"profile": "default"}) == {"id": "1"}
    assert request.call_args.args == ("POST", "/sessions")


@pytest.mark.asyncio
async def test_get(client):
    with transport(client, response(200, {"status": "running"})) as request:
        assert await client.get("/status") == {"status": "running"}
    assert request.call_args.args == ("GET", "/status")


@pytest.mark.asyncio
async def test_delete(client):
    with transport(client, response(200, {"ok": True})) as request:
        assert await client.delete("/sessions/1") == {"ok": True}
    assert request.call_args.args == ("DELETE", "/sessions/1")


@pytest.mark.asyncio
async def test_error_handling(client):
    with transport(client, response(404, {"detail": "Session 1 not found"})):
        with pytest.raises(BrowAPIError, match="Session 1 not found") as exc_info:
            await client.get("/nope")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_error_handling_plain_text(client):
    with transport(client, response(500, text="Internal Server Error")):
        with pytest.raises(BrowAPIError, match="Internal Server Error") as exc_info:
            await client.get("/broken")
        assert exc_info.value.status_code == 500
