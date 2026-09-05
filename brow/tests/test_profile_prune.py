import os
import time
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from brow import cli, current
from brow.cli import app

runner = CliRunner()

DAY = 86400


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    root = tmp_path / "profiles"
    root.mkdir()
    monkeypatch.setattr(cli, "PROFILES_DIR", root)
    monkeypatch.setattr("brow.cli.ensure_daemon", lambda: None)
    monkeypatch.delenv("BROW_PROFILE", raising=False)
    return root


def make(root, name, age_days, size=32):
    d = root / name
    d.mkdir()
    (d / "Cookies").write_bytes(b"x" * size)
    when = time.time() - age_days * DAY
    os.utime(d, (when, when))
    return d


def prune(argv, live=()):
    with patch("brow.cli.call", return_value=[{"profile": p} for p in live]):
        return runner.invoke(app, ["profile", "prune", *argv])


def test_reports_without_deleting_by_default(profiles):
    stale = make(profiles, "fp_54376_1247", age_days=90)

    result = prune([])

    assert stale.exists(), "a report-only run must not delete anything"
    assert "fp_54376_1247" in result.output
    assert "--yes" in result.output


def test_deletes_only_with_yes(profiles):
    stale = make(profiles, "old_junk", age_days=90)

    result = prune(["--yes"])

    assert not stale.exists()
    assert "freed" in result.output


def test_never_deletes_your_profile(profiles):
    mine = make(profiles, "personal", age_days=999)

    prune(["--yes"])

    assert mine.exists(), "personal holds your logins — pruning it is data loss, not cleanup"


def test_never_deletes_the_legacy_default_profile(profiles):
    legacy = make(profiles, "default", age_days=999)

    prune(["--yes"])

    assert legacy.exists()


def test_never_deletes_a_profile_a_live_session_holds(profiles):
    busy = make(profiles, "scraping_now", age_days=999)

    prune(["--yes"], live=["scraping_now"])

    assert busy.exists(), "deleting a profile under a running browser corrupts it"


def test_respects_the_age_cutoff(profiles):
    fresh = make(profiles, "yesterday", age_days=1)
    old = make(profiles, "ancient", age_days=60)

    prune(["--yes", "--days", "30"])

    assert fresh.exists()
    assert not old.exists()


def test_reports_nothing_to_do_when_all_profiles_are_fresh(profiles):
    make(profiles, "recent", age_days=2)

    result = prune(["--yes"])

    assert "Nothing to prune" in result.output


def test_honours_brow_profile_as_protected(profiles, monkeypatch):
    monkeypatch.setenv("BROW_PROFILE", "work")
    work = make(profiles, "work", age_days=999)

    prune(["--yes"])

    assert work.exists()
    assert current.default_profile() == "work"


def test_ignores_loose_files_next_to_the_profile_dirs(profiles):
    (profiles / "notes.txt").write_text("not a profile")
    make(profiles, "junk", age_days=99)

    result = prune(["--yes"])

    assert (profiles / "notes.txt").exists()
    assert "notes.txt" not in result.output


def test_reports_the_total_it_would_free(profiles):
    make(profiles, "a", age_days=99, size=2048)
    make(profiles, "b", age_days=99, size=2048)

    result = prune([])

    assert "2 profile(s)" in result.output
