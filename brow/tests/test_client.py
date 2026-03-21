import pytest
from unittest.mock import Mock, patch
from brow.client import BrowClient

@pytest.fixture
def client():
    return BrowClient()

@pytest.mark.asyncio
async def test_post(client):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "1"}
    mock_resp.raise_for_status = Mock()
    with patch.object(client._client, "post", return_value=mock_resp):
        result = await client.post("/sessions", json={"profile": "default"})
        assert result == {"id": "1"}

@pytest.mark.asyncio
async def test_get(client):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "running"}
    mock_resp.raise_for_status = Mock()
    with patch.object(client._client, "get", return_value=mock_resp):
        result = await client.get("/status")
        assert result == {"status": "running"}

@pytest.mark.asyncio
async def test_error_handling(client):
    mock_resp = Mock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "not found"}
    mock_resp.raise_for_status.side_effect = Exception("404")
    with patch.object(client._client, "get", return_value=mock_resp):
        with pytest.raises(Exception):
            await client.get("/nope")
