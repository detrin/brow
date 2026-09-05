import asyncio

import pytest

from benchmarks.stealth import runners, signals, sites


def probe(**overrides):
    base = {
        "webdriver": False,
        "automationKeys": [],
        "documentAutomationKeys": [],
        "hasChromeObject": True,
        "hasChromeRuntime": True,
        "plugins": 5,
        "pdfViewerEnabled": True,
        "userAgent": "Mozilla/5.0 Chrome/151.0.0.0 Safari/537.36",
        "headlessInUserAgent": False,
        "userAgentData": {"brands": ["Chromium", "Not=A?Brand"]},
        "platform": signals._host_platform(),
        "hardwareConcurrency": 14,
        "webgl": {"vendor": "Apple", "renderer": "ANGLE (Apple, Metal Renderer: M4 Max)"},
        "notificationPermission": "default",
        "permissionQueryState": "prompt",
        "nativeToString": True,
        "stackMentionsDriver": False,
        "timezone": "Europe/Prague",
        "screen": {"width": 1512, "height": 982},
        "window": {"outerWidth": 1280, "outerHeight": 720},
    }
    return {**base, **overrides}


def test_a_clean_browser_passes_every_check():
    s = signals.score(probe())
    assert s["passed"] == s["total"], [k for k, v in s["checks"].items() if not v["pass"]]


@pytest.mark.parametrize(
    "check,override",
    [
        ("navigator.webdriver absent", {"webdriver": True}),
        ("no automation globals", {"automationKeys": ["cdc_asdjflasutopfhvcZLmcfl_"]}),
        ("no automation globals", {"documentAutomationKeys": ["$cdc_asdjflasutopfhvcZLmcfl_"]}),
        ("window.chrome present", {"hasChromeObject": False}),
        ("chrome.runtime present", {"hasChromeRuntime": False}),
        ("plugins non-empty", {"plugins": 0}),
        ("PDF viewer enabled", {"pdfViewerEnabled": False}),
        ("no 'Headless' in UA", {"headlessInUserAgent": True}),
        ("client hints free of 'Headless'", {"userAgentData": {"brands": ["HeadlessChrome"]}}),
        ("window not larger than screen", {"screen": {"width": 800, "height": 600}}),
        ("hardware-accelerated WebGL", {"webgl": {"vendor": "Google", "renderer": "ANGLE (SwiftShader driver)"}}),
        ("hardware-accelerated WebGL", {"webgl": None}),
        ("notification permission not denied", {"notificationPermission": "denied"}),
        ("native function toString", {"nativeToString": False}),
        ("stack traces clean", {"stackMentionsDriver": True}),
        ("plausible core count", {"hardwareConcurrency": 1}),
        ("timezone matches host", {"timezone": None}),
        ("platform matches host OS", {"platform": "Nintendo64"}),
    ],
)
def test_each_signal_is_detected(check, override):
    checks = signals.score(probe(**override))["checks"]
    assert checks[check]["pass"] is False


def test_the_headless_permissions_contradiction_is_caught():
    bad = probe(notificationPermission="denied", permissionQueryState="prompt")
    assert signals.score(bad)["checks"]["permissions API self-consistent"]["pass"] is False


def test_consistently_denied_permissions_are_not_a_contradiction():
    ok = probe(notificationPermission="denied", permissionQueryState="denied")
    assert signals.score(ok)["checks"]["permissions API self-consistent"]["pass"] is True


def test_a_check_that_raises_counts_as_a_failure_not_a_crash():
    s = signals.score({"webdriver": False})
    assert s["passed"] < s["total"]
    assert any("check errored" in c["why"] for c in s["checks"].values())


@pytest.mark.parametrize("bad", [None, "boom", 42, []])
def test_a_non_object_probe_is_unusable(bad):
    assert signals.unusable(bad)


def test_a_probe_missing_values_is_unusable():
    assert "userAgent" in signals.unusable({"webdriver": False, "userAgent": None})


def test_a_complete_probe_is_usable():
    assert signals.unusable(probe()) is None


def test_a_transport_failure_is_never_reported_as_a_perfect_score():
    empty = {k: None for k in signals.REQUIRED_KEYS}
    assert signals.unusable(empty)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Just a moment...", "blocked"),
        ("Please complete the CAPTCHA", "blocked"),
        ("Our systems have detected unusual traffic", "blocked"),
        ("Example Domain\nThis domain is for use in illustrative examples.", "through"),
    ],
)
def test_block_pages_are_told_apart_from_real_ones(text, expected):
    assert sites.classify(200, text, None)[0] == expected


def test_a_403_is_a_block_even_without_a_marker():
    assert sites.classify(403, "a" * 200, None)[0] == "blocked"


def test_a_500_is_an_error_not_a_block():
    assert sites.classify(500, "a" * 200, None)[0] == "error"


def test_a_missing_page_is_an_error():
    assert sites.classify(200, None, None)[0] == "error"


def test_an_empty_page_is_an_error_not_a_pass():
    assert sites.classify(200, "  ", None)[0] == "error"


def test_the_control_site_must_actually_contain_its_marker():
    assert sites.classify(200, "a" * 200, "Example Domain")[0] == "error"


def test_every_registered_runner_has_a_matching_name():
    for name, cls in runners.REGISTRY.items():
        assert cls.name == name


def test_agent_browser_invokes_the_function_rather_than_passing_it_bare():
    assert runners.AgentBrowser.fn_forms[0].format(js="F") == "(F)()"


def test_probe_braces_survive_form_substitution():
    class Echo(runners.Runner):
        fn_forms = ("({js})()",)

        async def evaluate(self, js):
            self.seen = js
            return probe()

    r = Echo()
    asyncio.run(r.probe())
    assert r.seen.startswith("(async ()") and r.seen.endswith(")()")


def test_text_sample_is_truncated_and_never_returns_an_error_string():
    class Talkative(runners.Runner):
        async def evaluate(self, js):
            return "x" * 100

    assert len(asyncio.run(Talkative().text_sample(limit=10))) == 10


def test_text_sample_reports_nothing_rather_than_an_exception_message():
    class Broken(runners.Runner):
        async def evaluate(self, js):
            raise RuntimeError("boom")

    assert asyncio.run(Broken().text_sample()) is None


def test_probe_falls_back_until_a_form_produces_a_usable_result():
    class Fussy(runners.Runner):
        fn_forms = ("first", "second")

        def __init__(self):
            self.seen = []

        async def evaluate(self, js):
            self.seen.append(js)
            return {} if js == "first" else probe()

    r = Fussy()
    assert signals.unusable(asyncio.run(r.probe())) is None
    assert r.seen == ["first", "second"]


def test_probe_stops_at_the_first_usable_form():
    class Fine(runners.Runner):
        fn_forms = ("first", "second")

        def __init__(self):
            self.seen = []

        async def evaluate(self, js):
            self.seen.append(js)
            return probe()

    r = Fine()
    asyncio.run(r.probe())
    assert r.seen == ["first"]


def test_probe_records_the_exception_when_every_form_fails():
    class Broken(runners.Runner):
        fn_forms = ("a", "b")

        async def evaluate(self, js):
            raise RuntimeError("no such command")

    assert "no such command" in asyncio.run(Broken().probe())
