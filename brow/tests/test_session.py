import pytest

from brow.session import Session, SessionManager, is_browser_missing_error


@pytest.fixture
def manager():
    return SessionManager()


class FakeChromium:
    executable_path = "/chrome"

    def __init__(self, fail_channel=False):
        self.fail_channel = fail_channel
        self.calls = []

    async def launch_persistent_context(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_channel and "channel" in kwargs:
            raise RuntimeError("Chromium distribution 'chromium' is not found")
        return FakeContext()


class FakeContext:
    pages = []

    def on(self, *a):
        pass


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium


@pytest.fixture
def version(monkeypatch):
    from brow import stealth

    monkeypatch.setattr(stealth, "_major_version", lambda exe: "151")


async def test_headless_launch_asks_for_the_full_chromium_build(version):
    chromium = FakeChromium()
    await Session(id="1", profile="p", headless=True).launch(FakePlaywright(chromium), "/tmp/p")
    assert chromium.calls[0]["channel"] == "chromium"
    assert "Headless" not in chromium.calls[0]["user_agent"]


async def test_launch_falls_back_when_the_full_build_is_missing(version):
    chromium = FakeChromium(fail_channel=True)
    await Session(id="1", profile="p", headless=True).launch(FakePlaywright(chromium), "/tmp/p")
    assert len(chromium.calls) == 2
    assert "channel" not in chromium.calls[1]
    assert "user_agent" not in chromium.calls[1]


async def test_a_failure_unrelated_to_the_channel_is_not_swallowed(version):
    class AlwaysFails(FakeChromium):
        async def launch_persistent_context(self, **kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("disk full")

    chromium = AlwaysFails()
    with pytest.raises(RuntimeError, match="disk full"):
        await Session(id="1", profile="p", headless=True).launch(FakePlaywright(chromium), "/tmp/p")
    assert len(chromium.calls) == 2


async def test_headed_launch_leaves_the_user_agent_alone(version):
    chromium = FakeChromium()
    await Session(id="1", profile="p", headless=False).launch(FakePlaywright(chromium), "/tmp/p")
    assert "user_agent" not in chromium.calls[0]


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


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("Executable doesn't exist at /path/chromium", True),
        ("looks like Playwright was just installed. Run playwright install", True),
        ("please run patchright install chromium", True),
        ("Timeout 30000ms exceeded", False),
        ("Session 1 not found", False),
    ],
)
def test_is_browser_missing_error(msg, expected):
    assert is_browser_missing_error(Exception(msg)) is expected


def test_find_by_profile(manager):
    sid = manager.create("gmail", headless=True)
    assert manager.find_by_profile("gmail").id == sid
    assert manager.find_by_profile("nope") is None


def test_conflict_message_suggests_recovery(manager):
    sid = manager.create("gmail", headless=True)
    with pytest.raises(RuntimeError, match=f"session delete {sid}"):
        manager.create("gmail", headless=True)
