# Content-priority snapshots

**Date:** 2026-09-05
**Status:** approved

## Problem

`brow snapshot` can return a page's navigation chrome and none of its content,
with no indication that anything is missing.

Measured on `https://github.com/trending/python?since=daily`:

| | brow | agent-browser |
|---|---|---|
| snapshot bytes | 18,127 | 17,982 |
| repo rows in output | **0** | 14 |

The two snapshots cost the same tokens. One contains the answer; the other
contains 306 lines of GitHub header, ending mid-way through the spoken-language
dropdown at `menuitemradio "Oriya"`.

The benchmark agent's response to an empty snapshot is to fall back to `html`,
which returned 620,724 bytes (~155K tokens) — the single 383K-token outlier in
`benchmarks/results/report.md`.

### Four root causes

1. **Node-budget starvation.** `SNAPSHOT_JS` picks `NODE_LIMIT` of 200–400
   (`routes/browser.py:47-53`) and spends it in document order from
   `document.body`. Chrome comes first in the DOM, so on any page with a heavy
   header the budget is gone before the walk reaches `main`.

2. **Silent truncation.** The daemon sets `resp["truncated"]` and
   `resp["hint"]` (`routes/browser.py:412-414`), but `cli.py:244` prints only
   `result["tree"]`. The caller cannot tell a complete snapshot from a
   truncated one.

3. **`--locator` is dead.** The `/snapshot` route accepts it
   (`routes/browser.py:396`) and never passes it anywhere. Verified as a no-op
   on two different pages: it silently returns the whole page.

4. **`--search` is lossy twice over.** `filter_lines`
   (`snapshot.py:76`) caps at 10 matches with no notice, and it filters text
   that has *already* been truncated — so on GitHub trending,
   `--search "stars"` returned 1 byte.

Cause 1 makes the output wrong. Causes 2–4 mean the agent cannot detect or work
around it.

## Constraints

- **Keep the output format.** `[N] role "name"` lines, `[N]` as a click ref,
  markdown tables. Existing skill docs, playbooks, and benchmark comparability
  depend on it. Change *which nodes are selected* and *how truncation is
  reported*, nothing else.
- **Don't spend more tokens.** The point is a snapshot that contains the answer
  at the same size, not a bigger snapshot.

## Design

### 1. Content-root detection (pass 1)

New `findContentRoot()` runs before the walk:

- Prefer an explicit, visible landmark: `main, [role=main], article`.
- Otherwise score candidate blocks (`div`, `section`, `table`, `ul`, `ol` at
  depth ≤ 6) as `visibleTextLength + interactiveCount * 20`, penalising
  `nav`/`header`/`footer`/`aside` and `role=navigation`. Take the best scorer
  above a floor.
- Return `null` if nothing qualifies, or if the winner is `body` itself — a
  `body` content root is a no-op, and the walk falls back to per-container
  quotas alone.

### 2. Budget split and assembly (pass 2)

`NODE_LIMIT` stays adaptive (200/400/300) so the token profile does not move.
When a content root exists:

- `contentBudget = floor(NODE_LIMIT * 0.7)`, `chromeBudget = NODE_LIMIT - contentBudget`.
- Build the content subtree **first**, with `contentBudget`.
- Then walk `document.body` with `chromeBudget` plus whatever content left
  unspent. When that walk reaches `contentRoot`, splice in the already-built
  subtree instead of descending into it.

The splice is what preserves the format: output stays in exact document order
and reads identically to today, while *allocation* is content-first. Chrome can
only spend what content leaves behind.

This requires replacing the module-level `nodeCount`/`NODE_LIMIT` globals with a
`budget = {spent, cap}` object that can be reset between passes.

### 3. Per-container quotas

Inside the child loop, any container with more than 8 children is capped at
`max(20, floor(budget.cap * 0.2))` nodes. On hitting the cap it emits
`... N more items omitted (container cap)` and stops descending. Applied to
descendants, not to the root of each pass.

One huge widget can no longer monopolise the budget even within its own pass.

`sig()` is also fixed: it currently ends in `node.children.length`, so siblings
that differ by one child never collapse — which is how GitHub's 400-item
language list got through. New signature is `tag + firstClass + role`, with the
collapse threshold raised from 3 to 5 to compensate for the looser match.

### 4. Loud truncation

`_take_snapshot` returns a structured reason alongside the tree. The route puts
it in `hint`; `cli.py` prints it to **stderr** so piped stdout stays clean:

```
⚠ truncated: 412 of 1,180 nodes (main content reached)
```

The parenthetical says whether the content root was found and walked, which is
the difference between "you have the content, minus some chrome" and "you may
be missing the answer". Applies to `snapshot` and to the post-action snapshots
from `navigate`/`click`/`fill`/`key`/`select`.

### 5. `--locator` and `--search`

- **`--locator`** is passed through to `_take_snapshot` and used as the walk
  root. If it matches nothing, the route returns 400 — no silent fallback to
  the full page, which is what made the bug invisible.
- **`--search`** runs against untruncated text: in search mode the walk uses a
  raised budget and no per-node text clipping, then filters. Output is only the
  matching lines, so token cost stays low. `filter_lines` reports the total
  match count, the CLI prints `matched N lines, showing M` to stderr when
  `N > M`, and a new `--limit` flag (default 10, preserving current behaviour)
  raises the cap.

## Testing

TDD: fixture tests first, and each must fail against `main` for the stated
reason.

Static fixtures under `benchmarks/fixtures/static/` reproduce the failure
shapes:

- `nav-heavy.html` — a 400-item dropdown before a 30-row content table (the
  GitHub shape)
- `deep-chrome.html` — header/nav/footer plus a real `main`
- `no-landmark.html` — content in a plain `div`, no landmark to find

Browser-backed assertions (`brow/tests/test_snapshot_walker.py`, using the
existing ASGI + headless-Chromium fixture from `test_integration.py`):

- content rows appear in the snapshot for all three fixtures
- the truncation notice is emitted, and names the content-root outcome
- `--search` matches a string that lives inside a long cell
- `--locator` genuinely scopes; a non-matching locator is a 400
- **size regression guard**: snapshot bytes stay within a band on the fixture
  set, so the correctness win cannot silently trade away the token win

Unit tests extend `brow/tests/test_snapshot.py` for `filter_lines` limit and
match-count reporting.

## Out of scope

- Replacing the hand-rolled walker with Chrome's accessibility tree. A larger
  change; this fix is orthogonal and lands first.
- Re-running the benchmark. The numbers in `README.md` were measured with the
  old walker and become non-comparable once this lands; the changelog says so
  and the re-run is separate work.
