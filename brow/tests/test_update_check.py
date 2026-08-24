import json

import pytest

from brow import update_check


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(update_check, "UPDATE_CHECK_FILE", tmp_path / "update_check.json")


def test_no_notice_when_up_to_date(monkeypatch):
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "1.2.0")
    assert update_check.check_for_update(env={}) is None


def test_notice_when_a_newer_version_exists(monkeypatch):
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "1.3.0")
    notice = update_check.check_for_update(env={})
    assert notice is not None
    assert "1.3.0" in notice
    assert "1.2.0" in notice
    assert "pip install --upgrade brow-cli" in notice


def test_no_crash_when_current_version_is_unknown(monkeypatch):
    """Running from source without an installed package must not crash the CLI."""
    monkeypatch.setattr(update_check, "_current_version", lambda: None)
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "1.3.0")
    assert update_check.check_for_update(env={}) is None


def test_no_network_call_when_opted_out(monkeypatch):
    called = []
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: called.append(1) or "1.3.0")
    assert update_check.check_for_update(env={"BROW_NO_UPDATE_CHECK": "1"}) is None
    assert called == []


def test_no_crash_when_pypi_is_unreachable(monkeypatch):
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: None)
    assert update_check.check_for_update(env={}) is None


def test_result_is_cached_and_network_is_not_called_again(monkeypatch):
    calls = []
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: calls.append(1) or "1.3.0")

    first = update_check.check_for_update(env={})
    second = update_check.check_for_update(env={})

    assert first == second
    assert len(calls) == 1, "second call within the cache window must not hit the network again"


def test_cache_is_reused_across_a_stale_current_version_bump(monkeypatch, tmp_path):
    """A cached 'latest' must still fire a notice for a run whose installed
    version regressed or was never bumped, without re-hitting the network.
    """
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    calls = []
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: calls.append(1) or "1.3.0")
    update_check.check_for_update(env={})

    cache_path = update_check.UPDATE_CHECK_FILE
    data = json.loads(cache_path.read_text())
    assert data["latest"] == "1.3.0"

    notice = update_check.check_for_update(env={})
    assert "1.3.0" in notice
    assert len(calls) == 1


def test_corrupt_cache_file_does_not_crash(monkeypatch):
    update_check.UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
    update_check.UPDATE_CHECK_FILE.write_text("{not json")
    monkeypatch.setattr(update_check, "_current_version", lambda: "1.2.0")
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: "1.3.0")
    notice = update_check.check_for_update(env={})
    assert "1.3.0" in notice


@pytest.mark.parametrize(
    "latest,current,expect_notice",
    [
        ("1.3.0", "1.2.0", True),
        ("1.2.0", "1.2.0", False),
        ("1.2.0", "1.3.0", False),
        ("1.10.0", "1.9.0", True),
        ("1.2.0", "1.2.0.dev1", True),
        ("1.3.0", "1.3.0rc1", True),
        ("1.3.0rc2", "1.3.0rc1", True),
        ("not-a-version", "1.2.0", False),
    ],
)
def test_version_comparison(monkeypatch, latest, current, expect_notice):
    monkeypatch.setattr(update_check, "_current_version", lambda: current)
    monkeypatch.setattr(update_check, "_fetch_latest_version", lambda: latest)
    notice = update_check.check_for_update(env={})
    assert (notice is not None) == expect_notice
