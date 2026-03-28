from unittest.mock import patch
from typer.testing import CliRunner
from brow.cli import app
from brow.client import BrowAPIError

runner = CliRunner()

def test_daemon_status():
    with patch("brow.cli.daemon_running", return_value=True), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"status": "running", "sessions": 0}
        result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0

def test_session_new():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"id": "1", "profile": "default"}
        result = runner.invoke(app, ["session", "new"])
        assert result.exit_code == 0
        assert "1" in result.stdout

def test_session_list():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = [{"id": "1", "profile": "default", "headless": True, "pages": 1}]
        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0

def test_navigate():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"url": "https://example.com", "status": 200}
        result = runner.invoke(app, ["navigate", "-s", "1", "https://example.com"])
        assert result.exit_code == 0

def test_snapshot():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"tree": "heading \"Hello\""}
        result = runner.invoke(app, ["snapshot", "-s", "1"])
        assert result.exit_code == 0

def test_click():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["click", "-s", "1", "#btn"])
        assert result.exit_code == 0

def test_eval():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"result": 42, "stdout": ""}
        result = runner.invoke(app, ["eval", "-s", "1", "result = 42"])
        assert result.exit_code == 0

def test_fill_with_ref():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["fill", "-s", "1", "--ref", "29", "hello"])
        assert result.exit_code == 0

def test_fill_with_selector():
    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["fill", "-s", "1", "#input", "hello"])
        assert result.exit_code == 0

def test_fill_no_args():
    result = runner.invoke(app, ["fill", "-s", "1"])
    assert result.exit_code != 0

def test_api_error_surfaced():
    """Test that BrowAPIError from the client is caught and printed cleanly."""
    import asyncio
    async def _fail():
        raise BrowAPIError(400, "Profile 'personal' already in use by session 2")

    with patch("brow.cli.ensure_daemon"), \
         patch("brow.cli._client") as mock_client:
        mock_client.return_value.post = lambda *a, **k: _fail()
        result = runner.invoke(app, ["session", "new", "--profile", "personal"])
        assert result.exit_code == 2
        assert "Profile 'personal' already in use" in result.output
