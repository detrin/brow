from unittest.mock import Mock, patch

import pytest

from brow.client import BrowAPIError, BrowClient


@pytest.fixture
def client():
    return BrowClient()


@pytest.mark.asyncio
async def test_post(client):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {"id": "1"}
    with patch.object(client._client, "post", return_value=mock_resp):
        result = await client.post("/sessions", json={"profile": "default"})
        assert result == {"id": "1"}


@pytest.mark.asyncio
async def test_get(client):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {"status": "running"}
    with patch.object(client._client, "get", return_value=mock_resp):
        result = await client.get("/status")
        assert result == {"status": "running"}


@pytest.mark.asyncio
async def test_error_handling(client):
    mock_resp = Mock()
    mock_resp.status_code = 404
    mock_resp.is_error = True
    mock_resp.json.return_value = {"detail": "Session 1 not found"}
    with patch.object(client._client, "get", return_value=mock_resp):
        with pytest.raises(BrowAPIError, match="Session 1 not found") as exc_info:
            await client.get("/nope")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_error_handling_plain_text(client):
    mock_resp = Mock()
    mock_resp.status_code = 500
    mock_resp.is_error = True
    mock_resp.json.side_effect = ValueError("not json")
    mock_resp.text = "Internal Server Error"
    with patch.object(client._client, "get", return_value=mock_resp):
        with pytest.raises(BrowAPIError, match="Internal Server Error") as exc_info:
            await client.get("/broken")
        assert exc_info.value.status_code == 500
