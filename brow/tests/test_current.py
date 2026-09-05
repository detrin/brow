from unittest.mock import patch

import pytest

from brow import current


@pytest.fixture
def pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(current, "CURRENT_FILE", tmp_path / "current.json")
    monkeypatch.delenv("BROW_PROFILE", raising=False)
    return current.CURRENT_FILE


class FakeClient:
    def __init__(self, sessions=(), created="9"):
        self.sessions = list(sessions)
        self.created = created
        self.posts = []

    async def get(self, path):
        return self.sessions

    async def post(self, path, json=None):
        self.posts.append(json)
        return {"id": self.created}


def test_default_profile_is_personal(pointer):
    assert current.default_profile() == "personal"


def test_brow_profile_overrides(pointer, monkeypatch):
    monkeypatch.setenv("BROW_PROFILE", "work")
    assert current.default_profile() == "work"


@pytest.mark.asyncio
async def test_reuses_the_session_already_holding_the_profile(pointer):
    client = FakeClient(sessions=[{"id": "3", "profile": "personal"}])

    assert await current.resolve(client) == "3"
    assert client.posts == []


@pytest.mark.asyncio
async def test_creates_a_session_when_none_holds_the_profile(pointer):
    client = FakeClient(sessions=[{"id": "1", "profile": "scratch"}], created="4")

    assert await current.resolve(client) == "4"
    assert client.posts == [{"profile": "personal", "headless": True, "reclaim": True}]


@pytest.mark.asyncio
async def test_second_call_uses_the_cache_without_asking_the_daemon(pointer):
    await current.resolve(FakeClient(sessions=[{"id": "3", "profile": "personal"}]))

    class Exploding:
        async def get(self, path):
            raise AssertionError("cache miss: the common path must not hit the daemon")

    assert await current.resolve(Exploding()) == "3"


@pytest.mark.asyncio
async def test_cache_is_ignored_when_the_profile_changed(pointer, monkeypatch):
    """A cached id belongs to a profile. Reusing it under BROW_PROFILE=other would hand back someone else's browser."""
    await current.resolve(FakeClient(sessions=[{"id": "3", "profile": "personal"}]))

    monkeypatch.setenv("BROW_PROFILE", "work")
    client = FakeClient(sessions=[{"id": "3", "profile": "personal"}], created="7")

    assert await current.resolve(client) == "7"
    assert client.posts[0]["profile"] == "work"


@pytest.mark.asyncio
async def test_refresh_bypasses_the_cache(pointer):
    await current.resolve(FakeClient(sessions=[{"id": "3", "profile": "personal"}]))
    client = FakeClient(sessions=[{"id": "8", "profile": "personal"}])

    assert await current.resolve(client, refresh=True) == "8"


@pytest.mark.asyncio
async def test_headed_requests_a_visible_window(pointer):
    client = FakeClient(created="2")

    await current.resolve(client, headed=True)

    assert client.posts[0]["headless"] is False


def test_unreadable_pointer_is_treated_as_absent(pointer):
    pointer.write_text("{ not json")
    assert current.read() is None


def test_clear_is_idempotent(pointer):
    current.clear()
    current.write("5")
    current.clear()
    assert current.read() is None


def test_resolve_survives_a_corrupt_pointer(pointer):
    pointer.write_text("garbage")
    with patch.object(current, "write") as write:
        assert current.read() is None
    write.assert_not_called()
