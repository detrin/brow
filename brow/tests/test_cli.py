from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from brow.cli import app
from brow.client import BrowAPIError

runner = CliRunner()


def test_daemon_status():
    with patch("brow.cli.daemon_running", return_value=True), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"status": "running", "sessions": 0}
        result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0


def test_session_new():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"id": "1", "profile": "default"}
        result = runner.invoke(app, ["session", "new"])
        assert result.exit_code == 0
        assert "1" in result.stdout


def test_session_list():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = [{"id": "1", "profile": "default", "headless": True, "pages": 1}]
        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0


def test_navigate():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"url": "https://example.com", "status": 200}
        result = runner.invoke(app, ["navigate", "-s", "1", "https://example.com"])
        assert result.exit_code == 0


def test_snapshot():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"tree": 'heading "Hello"'}
        result = runner.invoke(app, ["snapshot", "-s", "1"])
        assert result.exit_code == 0


def test_click():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["click", "-s", "1", "#btn"])
        assert result.exit_code == 0


def test_eval():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"result": 42, "stdout": ""}
        result = runner.invoke(app, ["eval", "-s", "1", "result = 42"])
        assert result.exit_code == 0


def test_fill_with_ref():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["fill", "-s", "1", "--ref", "29", "hello"])
        assert result.exit_code == 0


def test_fill_with_selector():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True}
        result = runner.invoke(app, ["fill", "-s", "1", "#input", "hello"])
        assert result.exit_code == 0


def test_fill_no_args():
    result = runner.invoke(app, ["fill", "-s", "1"])
    assert result.exit_code != 0


def test_setup_runs_patchright():
    with patch("brow.cli.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 0
        assert "chromium" in mock_run.call_args[0][0]
        assert "Setup complete" in result.output


def test_setup_failure():
    with patch("brow.cli.subprocess.run", return_value=MagicMock(returncode=1)):
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 1


def test_api_error_surfaced():
    """Test that BrowAPIError from the client is caught and printed cleanly."""

    async def _fail():
        raise BrowAPIError(400, "Profile 'personal' already in use by session 2")

    with patch("brow.cli.ensure_daemon"), patch("brow.cli._client") as mock_client:
        mock_client.return_value.post = lambda *a, **k: _fail()
        result = runner.invoke(app, ["session", "new", "--profile", "personal"])
        assert result.exit_code == 2
        assert "Profile 'personal' already in use" in result.output


def test_fetch_surfaces_non_2xx_status():
    """A silent 401 is the worst possible output: it looks like success."""
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"status": 401, "body": "", "contentType": ""}
        result = runner.invoke(app, ["fetch", "-s", "1", "https://api.example.com/x"])
        assert result.exit_code == 0
        combined = result.stdout + (result.stderr or "")
        assert "401" in combined, f"status not surfaced: {combined!r}"


def test_fetch_stays_quiet_on_success():
    """The status line must not pollute normal output that gets piped to jq."""
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"status": 200, "body": '{"ok":true}', "contentType": "application/json"}
        result = runner.invoke(app, ["fetch", "-s", "1", "https://api.example.com/x"])
        assert result.exit_code == 0
        assert result.stdout.strip() == '{"ok":true}'


def test_page_new_accepts_positional_url():
    """AGENTS.md documents `brow page new -s 1 [url]`; it used to reject that."""
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"index": 1, "url": "https://example.org/"}
        result = runner.invoke(app, ["page", "new", "-s", "1", "https://example.org"])
        assert result.exit_code == 0, f"positional url rejected: {result.stdout}{result.stderr or ''}"


def test_click_until_reports_iteration_count():
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"ok": True, "done": True, "iterations": 7, "reason": "clickable is gone"}
        result = runner.invoke(app, ["click-until", "-s", "1", "button.next"])
        assert result.exit_code == 0
        assert "7" in result.stdout
        assert not (result.stderr or "").strip(), "a finished sweep should be quiet on stderr"


def test_click_until_flags_an_incomplete_sweep():
    """A capped sweep printing only its count reads as 'all done'; it isn't."""
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {
            "ok": True,
            "done": False,
            "iterations": 25,
            "reason": "hit max_iterations (25) — work may remain, re-run to continue",
        }
        result = runner.invoke(app, ["click-until", "-s", "1", "button.next", "--until-gone", ".row"])
        combined = result.stdout + (result.stderr or "")
        assert "max_iterations" in combined, f"incomplete sweep not flagged: {combined!r}"


def test_page_list_marks_active_tab():
    """Without a marker there is no way to know where the next command lands."""
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {
            "pages": [
                {"index": 0, "url": "https://a.example", "active": False},
                {"index": 1, "url": "https://b.example", "active": True},
            ]
        }
        result = runner.invoke(app, ["page", "list", "-s", "1"])
        assert result.exit_code == 0
        active_line = [ln for ln in result.stdout.splitlines() if "b.example" in ln][0]
        inactive_line = [ln for ln in result.stdout.splitlines() if "a.example" in ln][0]
        assert "*" in active_line
        assert "*" not in inactive_line
