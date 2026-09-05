from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from brow import current
from brow.cli import app
from brow.client import BrowAPIError

runner = CliRunner()


@pytest.fixture(autouse=True)
def pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(current, "CURRENT_FILE", tmp_path / "current.json")
    monkeypatch.delenv("BROW_PROFILE", raising=False)
    monkeypatch.setattr("brow.cli.ensure_daemon", lambda: None)


class Daemon:
    """Records every request path so a test can assert which session id the CLI addressed."""

    def __init__(self, sessions, fail_on=(), created="9"):
        self.sessions = sessions
        self.fail_on = set(fail_on)
        self.created = created
        self.paths = []

    async def get(self, path, **kwargs):
        self.paths.append(path)
        if path == "/sessions":
            return self.sessions
        return self._respond(path)

    async def post(self, path, **kwargs):
        self.paths.append(path)
        if path == "/sessions":
            self.sessions = self.sessions + [{"id": self.created, "profile": current.default_profile()}]
            return {"id": self.created}
        return self._respond(path)

    def _respond(self, path):
        for bad in self.fail_on:
            if f"/{bad}/" in path:
                raise BrowAPIError(404, f"Session {bad} not found")
        return {"url": "https://example.com", "status": 200, "tree": "root"}


def run(daemon, argv):
    with patch("brow.cli._client", lambda: daemon):
        return runner.invoke(app, argv)


def browser_paths(daemon):
    return [p for p in daemon.paths if p.startswith("/browser/")]


def test_bare_command_reuses_the_session_holding_your_profile():
    daemon = Daemon([{"id": "3", "profile": "personal"}])

    result = run(daemon, ["url"])

    assert result.exit_code == 0
    assert browser_paths(daemon) == ["/browser/3/url"]


def test_bare_command_starts_a_session_when_there_is_none():
    daemon = Daemon([], created="1")

    result = run(daemon, ["url"])

    assert result.exit_code == 0
    assert "/sessions" in daemon.paths
    assert browser_paths(daemon) == ["/browser/1/url"]


def test_never_addresses_a_session_named_none():
    """The old bare path built /browser/None/... and showed the user a leaked Python None."""
    daemon = Daemon([{"id": "3", "profile": "personal"}])

    result = run(daemon, ["url"])

    assert "None" not in "".join(daemon.paths)
    assert "Session None not found" not in result.output


def test_explicit_session_flag_still_wins():
    daemon = Daemon([{"id": "3", "profile": "personal"}])

    run(daemon, ["url", "-s", "7"])

    assert browser_paths(daemon) == ["/browser/7/url"]
    assert "/sessions" not in daemon.paths


def test_a_stale_pointer_reresolves_instead_of_failing():
    """A cached id outliving its session is routine; the user should never see it."""
    current.write("4")
    daemon = Daemon([{"id": "6", "profile": "personal"}], fail_on={"4"})

    result = run(daemon, ["url"])

    assert result.exit_code == 0, result.output
    assert browser_paths(daemon) == ["/browser/4/url", "/browser/6/url"]


def test_a_genuine_404_is_still_reported():
    daemon = Daemon([{"id": "6", "profile": "personal"}], fail_on={"4", "6"})
    current.write("4")

    result = run(daemon, ["url"])

    assert result.exit_code == 2
    assert "not found" in result.output


def test_resolution_is_not_retried_more_than_once():
    daemon = Daemon([{"id": "6", "profile": "personal"}], fail_on={"4", "6"})
    current.write("4")

    run(daemon, ["url"])

    assert daemon.paths.count("/sessions") == 1


def test_session_new_records_the_pointer_for_the_default_profile():
    daemon = Daemon([], created="2")

    run(daemon, ["session", "new"])

    assert current.read() == "2"


def test_session_new_with_another_profile_leaves_the_pointer_alone():
    current.write("3")
    daemon = Daemon([], created="5")

    run(daemon, ["session", "new", "--profile", "scratch"])

    assert current.read() == "3"


class Recorder(Daemon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bodies = []

    async def post(self, path, **kwargs):
        self.bodies.append((path, kwargs.get("json")))
        return await super().post(path, **kwargs)


def test_session_new_defaults_to_your_profile_not_default():
    daemon = Recorder([], created="2")

    run(daemon, ["session", "new"])

    assert daemon.bodies[0][1]["profile"] == "personal"


def test_session_new_honours_brow_profile(monkeypatch):
    monkeypatch.setenv("BROW_PROFILE", "work")
    daemon = Recorder([], created="2")

    run(daemon, ["session", "new"])

    assert daemon.bodies[0][1]["profile"] == "work"


def test_state_save_resolves_the_session_too():
    """state save passes the id in the body, not the path, so path resolution alone would leave it None."""
    daemon = Recorder([{"id": "3", "profile": "personal"}])

    run(daemon, ["state", "save", "snap"])

    body = next(b for p, b in daemon.bodies if p == "/states/save")
    assert body["session_id"] == "3"


def test_login_asks_for_a_visible_window_and_records_the_pointer():
    daemon = Recorder([], created="5")

    result = run(daemon, ["login", "https://mail.google.com"])

    path, body = daemon.bodies[0]
    assert path == "/sessions"
    assert body["headless"] is False
    assert body["url"] == "https://mail.google.com"
    assert current.read() == "5"
    assert result.exit_code == 0
