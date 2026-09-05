"""Browser-backed tests for the snapshot walker.

The walker is JavaScript evaluated in the page, so these tests drive a real
headless Chromium against static fixtures. Each fixture reproduces a shape that
starved the document-order walk: the answer was missing from the snapshot while
the page's navigation chrome filled it.
"""

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from brow.daemon import create_app

FIXTURES = Path(__file__).parents[2] / "benchmarks" / "fixtures" / "static"


def fixture_url(name):
    path = FIXTURES / name
    assert path.exists(), f"missing fixture {path}"
    return path.as_uri()


@pytest.fixture
async def client():
    app = create_app()
    async with app.router.lifespan_context(app) as _:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
async def sid(client):
    r = await client.post("/sessions", json={"profile": "walker", "headless": True})
    assert r.status_code == 200
    session_id = r.json()["id"]
    yield session_id
    await client.delete(f"/sessions/{session_id}")


async def snap(client, sid, fixture, **params):
    r = await client.post(f"/browser/{sid}/navigate", json={"url": fixture_url(fixture)})
    assert r.status_code == 200
    r = await client.get(f"/browser/{sid}/snapshot", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# --- content survives heavy chrome -----------------------------------------


async def test_nav_heavy_reaches_main_content(client, sid):
    """A 180-item dropdown before <main> must not cost us the repo rows."""
    body = await snap(client, sid, "nav-heavy.html")
    tree = body["tree"]

    assert tree.count("stars today") >= 8, tree[-2000:]
    assert "acme / alpha" in tree
    assert "acme / juliett" in tree, "last row missing — content budget ran out"


async def test_deep_chrome_reaches_table(client, sid):
    """A 120-item nav and a 60-item sidebar must not cost us the order table."""
    body = await snap(client, sid, "deep-chrome.html")
    tree = body["tree"]

    assert "Order 1" in tree
    assert "Customer 1" in tree
    assert "| Order | Customer | Total | Status |" in tree, "table headers missing"
    assert "more rows" in tree, "row cap should say how many rows it withheld"


async def test_no_landmark_finds_content_by_density(client, sid):
    """With no <main>/<article>, the prose block still has to win the budget."""
    body = await snap(client, sid, "no-landmark.html")
    tree = body["tree"]

    assert "Post title 1" in tree
    assert "Post title 12" in tree, "last post missing — content budget ran out"
    assert "Nav link 1" in tree, "some chrome should still be reported"
    assert "div.posts" in body.get("hint", ""), "hint should name the content root it picked"


async def test_varied_cards_are_never_collapsed(client, sid):
    """Regression guard: structurally varied listing cards must all survive.

    Loosening the sibling signature or applying a container quota to content
    would compress these into '... N similar items omitted' — the failure mode
    that would break every scraping task.
    """
    body = await snap(client, sid, "varied-cards.html")
    tree = body["tree"]

    for i in range(1, 13):
        assert f"Widget {i}" in tree, f"card {i} missing from snapshot"
    assert not body.get("truncated"), "a 12-card page should not truncate"


async def test_content_survives_a_budget_exhausting_header(client, sid):
    """Reaching the content subtree must not depend on the chrome pass's budget.

    The content pass builds the subtree first, but pass 2 walks the document in
    order and used to bail on `out()` before it ever reached the splice point —
    throwing away the whole content subtree it had just paid for. A big enough
    header was all it took.
    """
    body = await snap(client, sid, "huge-header.html")
    tree = body["tree"]

    assert "Search results" in tree, "content subtree was discarded entirely"
    kept = [i for i in range(1, 16) if f"RESULT{i}" in tree]
    assert len(kept) >= 12, f"only {len(kept)}/15 results survived: {kept}"
    assert "Header link 1" in tree, "some chrome should still be reported"


async def test_menu_inside_content_does_not_eat_the_content_budget(client, sid):
    """A dropdown parked in <main> is not content, however big it is.

    Two things conspired here: the container quota was disabled inside the
    content pass, and the prose score counted the whitespace *between* 400 menu
    items as prose — enough for the menu to outscore the products next to it. The
    products are what the caller came for.
    """
    body = await snap(client, sid, "menu-in-main.html")
    tree = body["tree"]

    kept = [i for i in range(1, 13) if f"PRODUCT{i}" in tree]
    assert len(kept) == 12, f"only {len(kept)}/12 products survived: {kept}"
    assert "container cap" in tree, "the menu should be reported as capped, not silently walked"
    assert "Language option number 1" in tree, "the menu should still be reachable"


async def test_refs_ascend_in_output_order(client, sid):
    """[N] must still count up as the caller reads down the tree.

    Building content before chrome assigns refs out of document order, which
    would have the caller clicking [1] near the bottom of the page.
    """
    for fixture in ("huge-header.html", "nav-heavy.html", "icon-links.html"):
        body = await snap(client, sid, fixture)
        refs = [int(n) for n in re.findall(r"^\s*\[(\d+)\]", body["tree"], re.M)]

        assert refs, f"{fixture}: no refs at all"
        assert refs == sorted(refs), f"{fixture}: refs out of order: {refs[:20]}"
        assert refs == list(range(1, len(refs) + 1)), f"{fixture}: refs not contiguous: {refs[:20]}"


async def test_refs_resolve_to_the_element_they_label(client, sid):
    """Renumbering must move the DOM attributes with the numbers."""
    body = await snap(client, sid, "huge-header.html")
    ref = re.search(r'\[(\d+)\] a "Buy widget 3"', body["tree"])
    assert ref, body["tree"][-1500:]

    r = await client.post(
        f"/eval/{sid}",
        json={
            "code": "result = await page.eval_on_selector("
            f"'[data-brow-ref=\"{ref.group(1)}\"]', 'el => el.textContent.trim()')"
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "Buy widget 3", r.json()


async def test_icon_bearing_elements_survive(client, sid):
    """An inline <svg> icon must not delete the element that contains it.

    sig() called className.split() on every sibling, and on an SVG element
    className is an SVGAnimatedString — the throw escaped buildTree and the
    parent's catch swallowed the whole subtree. Every icon link, star count and
    icon button on the page vanished with no error anywhere.
    """
    body = await snap(client, sid, "icon-links.html")
    tree = body["tree"]

    for i in range(1, 13):
        assert f"package-{i}" in tree, f"repo link {i} lost with its icon"
        assert f"{40 + i} stars today" in tree, f"star count {i} lost with its icon"
    assert "Star" in tree, "icon button lost"
    assert "walker error" not in body.get("hint", ""), body.get("hint")


async def test_walker_errors_are_reported_not_swallowed(client, sid):
    """No fixture may drop a subtree silently — the hint has to say so."""
    for fixture in ("icon-links.html", "nav-heavy.html", "prose-article.html"):
        body = await snap(client, sid, fixture)
        assert "walker error" not in body.get("hint", ""), f"{fixture}: {body.get('hint')}"


async def test_link_dense_article_keeps_its_prose(client, sid):
    """A wiki-shaped page is interactive-dense, but its prose is the answer.

    The interactive-dense heuristic drops non-interactive nodes past 70% of the
    budget. Applied inside the content pass it deleted exactly the paragraphs
    the pass had been given the budget to keep.
    """
    body = await snap(client, sid, "prose-article.html")
    tree = body["tree"]

    kept = [p for p in range(1, 21) if f"PARA{p}START" in tree]
    assert len(kept) == 20, f"only {len(kept)}/20 paragraphs survived: {kept}"
    # Chrome may still be trimmed; the article itself must be reported complete.
    assert "main#content complete" in body.get("hint", ""), body.get("hint")


# --- truncation is reported -------------------------------------------------


async def test_truncation_is_reported_on_stderr_channel(client, sid):
    """Omitted nodes must be announced, and the notice must say what was kept."""
    body = await snap(client, sid, "nav-heavy.html")

    assert body.get("truncated") is True
    hint = body["hint"]
    assert hint.startswith("⚠ truncated:"), hint
    assert " nodes (" in hint
    assert "main complete" in hint, hint


async def test_truncation_counts_are_coherent(client, sid):
    """'N of M nodes' must not claim more nodes kept than the page contains."""
    body = await snap(client, sid, "nav-heavy.html")
    kept, total = (int(n.replace(",", "")) for n in re.findall(r"([\d,]+) of ([\d,]+) nodes", body["hint"])[0])

    assert 0 < kept <= total, f"incoherent counts in {body['hint']!r}"


async def test_untruncated_page_reports_nothing(client, sid):
    body = await snap(client, sid, "varied-cards.html")
    assert "hint" not in body
    assert "truncated" not in body


# --- --search --------------------------------------------------------------


async def test_search_matches_content_the_default_walk_omits(client, sid):
    """--search runs against the untruncated walk, not the truncated output."""
    body = await snap(client, sid, "nav-heavy.html", search="stars today")
    lines = [ln for ln in body["tree"].split("\n") if ln.strip()]

    assert len(lines) == 10, body["tree"]
    assert any("1,204 stars today" in ln for ln in lines)


async def test_search_reaches_table_rows_beyond_the_row_cap(client, sid):
    """Row 20 is past MAX_TABLE_ROWS — search still has to find it."""
    body = await snap(client, sid, "deep-chrome.html", search="Order 20")

    assert "Order 20" in body["tree"]


async def test_search_reaches_items_past_a_container_quota(client, sid):
    """Search must not inherit the container cap.

    The cap exists to save tokens, and in search mode it saves none — only
    matching lines are returned. Applied there it just made the 400th item of a
    dropdown unfindable while the 1st was fine, which is indistinguishable from
    the item not existing.
    """
    for item in ("Language option number 1", "Language option number 400"):
        body = await snap(client, sid, "menu-in-main.html", search=item)

        assert item in body["tree"], f"{item!r} unfindable: {body['tree']!r}"


# 140 nav links, each reported as a link line plus its text line.
NAV_LINK_LINES = 280


async def test_search_reports_matches_it_withheld(client, sid):
    body = await snap(client, sid, "no-landmark.html", search="Nav link", limit=5)
    lines = [ln for ln in body["tree"].split("\n") if ln.strip()]

    assert len(lines) == 5
    assert f"matched {NAV_LINK_LINES} lines, showing 5" in body["hint"], body.get("hint")


async def test_search_limit_raises_the_cap(client, sid):
    body = await snap(client, sid, "no-landmark.html", search="Nav link", limit=400)
    lines = [ln for ln in body["tree"].split("\n") if ln.strip()]

    assert len(lines) == NAV_LINK_LINES
    assert "matched" not in body.get("hint", "")


# --- --locator -------------------------------------------------------------


async def test_locator_scopes_the_walk(client, sid):
    body = await snap(client, sid, "nav-heavy.html", locator="main")
    tree = body["tree"]

    assert "acme / alpha" in tree
    assert "Abkhazian" not in tree, "--locator did not scope: nav content leaked in"
    assert "Trending repositories" in tree


async def test_locator_that_matches_nothing_is_an_error(client, sid):
    r = await client.post(f"/browser/{sid}/navigate", json={"url": fixture_url("nav-heavy.html")})
    assert r.status_code == 200

    r = await client.get(f"/browser/{sid}/snapshot", params={"locator": "#does-not-exist"})
    assert r.status_code == 400, "a non-matching locator must not silently return the whole page"
    assert "matched no elements" in r.json()["detail"]


# --- size guard ------------------------------------------------------------

# Correctness must not be bought with tokens: these are the sizes measured for
# the content-priority walk, with headroom. A jump here means the walk got
# greedier, not smarter.
SIZE_BUDGET = {
    "nav-heavy.html": 12_000,
    "deep-chrome.html": 12_000,
    "no-landmark.html": 12_000,
    "varied-cards.html": 4_000,
    "icon-links.html": 12_000,
    "prose-article.html": 20_000,
    "huge-header.html": 14_000,
    "menu-in-main.html": 12_000,
}


@pytest.mark.parametrize("fixture,cap", SIZE_BUDGET.items())
async def test_snapshot_stays_within_size_budget(client, sid, fixture, cap):
    body = await snap(client, sid, fixture)
    size = len(body["tree"].encode())

    assert size <= cap, f"{fixture} snapshot grew to {size} bytes (cap {cap})"


# --- post-action snapshots carry the same notice ---------------------------


async def test_click_response_reports_truncation(client, sid):
    r = await client.post(f"/browser/{sid}/navigate", json={"url": fixture_url("nav-heavy.html")})
    assert r.status_code == 200

    r = await client.post(f"/browser/{sid}/click", json={"selector": "summary"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("truncated") is True
    assert body["hint"].startswith("⚠ truncated:")
