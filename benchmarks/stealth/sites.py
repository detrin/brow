BLOCK_MARKERS = (
    "just a moment",
    "checking your browser",
    "verifying you are human",
    "attention required",
    "access denied",
    "unusual traffic",
    "are you a robot",
    "enable javascript and cookies to continue",
    "pardon our interruption",
    "request unsuccessful",
    "blocked",
    "captcha",
)

SITES = [
    {
        "id": "example",
        "url": "https://example.com",
        "expect": "Example Domain",
        "note": "Control. A runner failing here is broken, not blocked.",
    },
    {
        "id": "alza",
        "url": "https://www.alza.cz/search.htm?exps=insekticid",
        "expect": None,
        "note": "Blocked agent-browser and let brow through in manual testing; the case that motivated this harness.",
    },
    {
        "id": "google-search",
        "url": "https://www.google.com/search?q=site:example.com",
        "expect": None,
        "note": "Soft-blocks aggressively on automation signals.",
    },
    {
        "id": "sannysoft",
        "url": "https://bot.sannysoft.com/",
        "expect": None,
        "note": "Reference detector page; read the per-signal table in the JSON output.",
    },
]


def classify(status, text, expect):
    if text is None:
        return "error", "no page text"
    low = text.lower()
    hit = next((m for m in BLOCK_MARKERS if m in low), None)
    if hit:
        return "blocked", f"page says {hit!r}"
    if status is not None and status in (403, 429):
        return "blocked", f"HTTP {status}"
    if status is not None and status >= 500:
        return "error", f"HTTP {status}"
    if expect and expect.lower() not in low:
        return "error", f"expected {expect!r} in page"
    if len(low.strip()) < 40:
        return "error", "page essentially empty"
    return "through", f"HTTP {status}" if status else "ok"
