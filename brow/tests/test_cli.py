from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from brow.cli import app
from brow.client import BrowAPIError

runner = CliRunner()


@pytest.fixture(autouse=True)
def inert_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("brow.cli._client", lambda: client)
    return client


def test_daemon_status():
    with patch("brow.cli.daemon_running", return_value=True), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"status": "running", "sessions": 0}
        result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0


def test_daemon_start_wait_checks_requested_port():
    with (
        patch("brow.cli.daemon_running", return_value=False),
        patch("brow.cli.subprocess.Popen"),
        patch("brow.cli.time.sleep"),
        patch("brow.cli.set_daemon_port") as persist_port,
        patch("brow.cli._daemon_healthy", side_effect=[False, True]) as healthy,
    ):
        result = runner.invoke(app, ["daemon", "start", "--port", "20990", "--wait"])

    assert result.exit_code == 0, result.output
    persist_port.assert_called_once_with(20990)
    assert all(call.args == (20990,) for call in healthy.call_args_list)
    assert "20990" in result.output


def test_ensure_daemon_surfaces_an_available_update():
    with (
        patch("brow.cli.check_for_update", return_value="brow 1.3.0 is available (you have 1.2.0)."),
        patch("brow.cli._daemon_healthy", return_value=True),
        patch("brow.cli.run_async") as mock_run,
    ):
        mock_run.return_value = [{"id": "1", "profile": "default", "headless": True, "pages": 1}]
        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0
        assert "1.3.0 is available" in (result.stderr or result.output)


def test_ensure_daemon_stays_quiet_when_up_to_date():
    with (
        patch("brow.cli.check_for_update", return_value=None),
        patch("brow.cli._daemon_healthy", return_value=True),
        patch("brow.cli.run_async") as mock_run,
    ):
        mock_run.return_value = [{"id": "1", "profile": "default", "headless": True, "pages": 1}]
        result = runner.invoke(app, ["session", "list"])
        assert result.exit_code == 0
        assert "is available" not in (result.stderr or result.output)


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


def test_setup_upgrade_bumps_patchright_before_installing_chromium():
    """`--upgrade` must update the pip package first, then fetch the Chromium
    build that new version expects — installing chromium alone would just
    re-fetch the build for whatever version was already pinned.
    """
    with (
        patch("brow.cli.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
        patch("brow.cli.daemon_running", return_value=False),
    ):
        result = runner.invoke(app, ["setup", "--upgrade"])
        assert result.exit_code == 0
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("pip" in c and "--upgrade" in c and "patchright" in c for c in calls)
        assert any("chromium" in c for c in calls)
        # pip upgrade must run before the chromium install picks up the new version
        pip_idx = next(i for i, c in enumerate(calls) if "pip" in c)
        chromium_idx = next(i for i, c in enumerate(calls) if "chromium" in c)
        assert pip_idx < chromium_idx


def test_setup_upgrade_restarts_a_running_daemon():
    """The daemon is a separate process that already imported the old
    patchright — it won't pick up an upgrade without a restart.
    """
    with (
        patch("brow.cli.subprocess.run", return_value=MagicMock(returncode=0)),
        patch("brow.cli.daemon_running", return_value=True),
        patch("brow.cli.stop_daemon") as mock_stop,
    ):
        result = runner.invoke(app, ["setup", "--upgrade"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()


def test_setup_upgrade_failure_stops_before_installing_chromium():
    with (
        patch("brow.cli.subprocess.run", return_value=MagicMock(returncode=1)) as mock_run,
        patch("brow.cli.daemon_running", return_value=False),
    ):
        result = runner.invoke(app, ["setup", "--upgrade"])
        assert result.exit_code == 1
        assert mock_run.call_count == 1


def test_setup_without_upgrade_does_not_touch_pip():
    with patch("brow.cli.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        runner.invoke(app, ["setup"])
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert not any("pip" in c for c in calls)


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


def test_replay_exits_nonzero_on_a_failed_step(tmp_path):
    """A playbook with a failed step must not look like success to a caller checking $?."""
    pb = tmp_path / "pb.yaml"
    pb.write_text("steps:\n  - action: click\n    selector: '#x'\n")
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"results": [{"action": "click", "ok": False, "error": "not found"}]}
        result = runner.invoke(app, ["replay", str(pb), "-s", "1"])
        assert result.exit_code == 1


def test_replay_exits_zero_when_all_steps_succeed(tmp_path):
    pb = tmp_path / "pb.yaml"
    pb.write_text("steps:\n  - action: click\n    selector: '#x'\n")
    with patch("brow.cli.ensure_daemon"), patch("brow.cli.run_async") as mock_run:
        mock_run.return_value = {"results": [{"action": "click", "ok": True}]}
        result = runner.invoke(app, ["replay", str(pb), "-s", "1"])
        assert result.exit_code == 0


def test_run_sends_file_contents_as_eval_code(tmp_path):
    script = tmp_path / "workflow.py"
    script.write_text("result = {'processed': 1}\n")
    with patch("brow.cli.call") as mock_call:
        mock_call.return_value = {"stdout": "", "result": {"processed": 1}}
        result = runner.invoke(app, ["run", str(script), "-s", "1"])
        assert result.exit_code == 0
        assert "processed" in result.stdout
        assert "result = {'processed': 1}" in mock_call.call_args.kwargs["json"]["code"]


def test_run_passes_args_into_the_script_namespace(tmp_path):
    script = tmp_path / "workflow.py"
    script.write_text("print(args['query'])\n")
    with patch("brow.cli.call") as mock_call:
        mock_call.return_value = {"stdout": "", "result": None}
        result = runner.invoke(app, ["run", str(script), "-s", "1", "--arg", "query=widgets"])
        assert result.exit_code == 0
        code = mock_call.call_args.kwargs["json"]["code"]
        assert 'args = {"query": "widgets"}' in code
        assert "print(args['query'])" in code
