import pytest

from brow import stealth


@pytest.fixture
def version(monkeypatch):
    def set(text):
        monkeypatch.setattr(stealth, "_major_version", lambda exe: text)

    return set


def test_headless_uses_the_full_chromium_build(version):
    version("151")
    kwargs = stealth.launch_kwargs("/tmp/p", True, "/chrome")
    assert kwargs["channel"] == "chromium"


def test_headed_does_not_override_anything(version):
    version("151")
    kwargs = stealth.launch_kwargs("/tmp/p", False, "/chrome")
    assert "channel" not in kwargs
    assert "user_agent" not in kwargs


def test_headless_user_agent_does_not_say_headless(version):
    version("151")
    ua = stealth.launch_kwargs("/tmp/p", True, "/chrome")["user_agent"]
    assert "Headless" not in ua
    assert "Chrome/151.0.0.0" in ua


def test_user_agent_omitted_when_version_is_undetectable(version):
    version(None)
    assert "user_agent" not in stealth.launch_kwargs("/tmp/p", True, "/chrome")


def test_user_agent_omitted_on_unknown_platform(monkeypatch, version):
    version("151")
    monkeypatch.setattr(stealth.platform, "system", lambda: "Plan9")
    assert stealth.user_agent("/chrome") is None


@pytest.mark.parametrize(
    "system,token",
    [("Darwin", "Macintosh"), ("Windows", "Windows NT"), ("Linux", "X11; Linux")],
)
def test_user_agent_matches_the_host_os(monkeypatch, version, system, token):
    version("151")
    monkeypatch.setattr(stealth.platform, "system", lambda: system)
    assert token in stealth.user_agent("/chrome")


def test_version_detection_survives_a_missing_binary():
    assert stealth._major_version("/nonexistent/chrome-binary") is None


def test_version_parsed_from_chrome_output(monkeypatch):
    class Result:
        stdout = "Google Chrome for Testing 151.0.7922.34\n"

    monkeypatch.setattr(stealth.subprocess, "run", lambda *a, **k: Result())
    assert stealth._major_version("/chrome-for-version-parsing") == "151"


def test_unparseable_version_output_is_not_guessed(monkeypatch):
    class Result:
        stdout = "some other tool v9\n"

    monkeypatch.setattr(stealth.subprocess, "run", lambda *a, **k: Result())
    assert stealth._major_version("/chrome-with-odd-output") is None


def test_stealth_args_are_not_shared_between_sessions(version):
    version("151")
    a = stealth.launch_kwargs("/tmp/a", True, "/chrome")
    a["args"].append("--extra")
    b = stealth.launch_kwargs("/tmp/b", True, "/chrome")
    assert "--extra" not in b["args"]
