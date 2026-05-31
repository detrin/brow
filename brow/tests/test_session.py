import pytest

from brow.session import SessionManager


@pytest.fixture
def manager():
    return SessionManager()


def test_create_session(manager):
    sid = manager.create("default", headless=True)
    assert sid == "1"
    assert "1" in manager.sessions


def test_sequential_ids(manager):
    s1 = manager.create("a", headless=True)
    s2 = manager.create("b", headless=True)
    assert s1 == "1"
    assert s2 == "2"


def test_delete_session(manager):
    sid = manager.create("default", headless=True)
    manager.delete(sid)
    assert sid not in manager.sessions


def test_delete_nonexistent(manager):
    with pytest.raises(KeyError):
        manager.delete("999")


def test_get_session(manager):
    sid = manager.create("default", headless=True)
    session = manager.get(sid)
    assert session.profile == "default"


def test_max_sessions(manager, monkeypatch):
    monkeypatch.setattr("brow.session.MAX_SESSIONS", 2)
    manager.create("a", headless=True)
    manager.create("b", headless=True)
    with pytest.raises(RuntimeError, match="Max sessions"):
        manager.create("c", headless=True)


def test_list_sessions(manager):
    manager.create("a", headless=True)
    manager.create("b", headless=True)
    result = manager.list()
    assert len(result) == 2


def test_duplicate_profile(manager):
    manager.create("gmail", headless=True)
    with pytest.raises(RuntimeError, match="already in use"):
        manager.create("gmail", headless=True)
