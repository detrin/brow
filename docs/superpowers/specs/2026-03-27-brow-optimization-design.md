# Brow Optimization Design — Ref Engine, Smart Snapshots, Agent Loop

**Date:** 2026-03-27
**Status:** Approved
**Context:** Benchmarks show brow uses +8% more tokens than playwright-cli on average, primarily due to tool call overhead (session setup, explicit snapshots after actions, string selectors). brow wins on complex pages (-35% to -64%) but loses on simple/multi-step tasks (+106% to +188%). This design addresses all three layers: API, snapshot compression, and agent loop.

## Phase 1: Ref Engine + Auto-Snapshot

### 1.1 Ref System

Snapshots assign numeric refs to interactive elements. The agent uses `ref=5` instead of `selector="text=Photosynthesis"`.

**Implementation:**

1. JS `buildTree()` injects `data-brow-ref="N"` attributes onto each interactive element during traversal. Counter starts at 1, increments for elements in the INTERACTIVE set (a, button, input, select, textarea, option, details, summary, menuitem) plus any element with an explicit `role` attribute that implies interactivity (e.g., `role="button"`, `role="tab"`, `role="link"`).

2. Snapshot output includes refs inline:
   ```
   [1] link "Home" href="/"
   [2] link "About" href="/about"
   heading "Welcome" level=1
   paragraph "Some text here"
   [3] textbox "Email"
   [4] button "Submit"
   ```
   Non-interactive elements have no ref.

3. No server-side ref map needed. When the agent sends `ref=5`, the endpoint resolves it to CSS selector `[data-brow-ref="5"]` — guaranteed unique.

4. Before each new snapshot, a cleanup pass removes all existing `data-brow-ref` attributes, then reassigns fresh refs. Refs from a previous snapshot become invalid.

5. Click/fill/select still accept `selector=` as fallback (backward compatible).

### 1.2 Auto-Snapshot After Actions

Mutation endpoints return the updated page state automatically, eliminating the action→snapshot→read cycle.

**Endpoints affected:**
- `POST /browser/{sid}/click`
- `POST /browser/{sid}/fill`
- `POST /browser/{sid}/select`
- `POST /browser/{sid}/navigate`
- `POST /browser/{sid}/key`

**Response format:**
```json
{
  "status": "ok",
  "snapshot": "[1] link \"Home\"\n[2] button \"Next\"...",
  "truncated": false
}
```

- Optional query param `?snapshot=false` to suppress
- Runs `waitForLoadState("domcontentloaded")` before snapshotting to catch post-click page transitions
- Uses the same JS as standalone snapshot endpoint (pruning, dedup, node cap, ref assignment)

### 1.3 Combined Session + Navigate

`brow_session_new` gains optional `--url <url>` parameter.

If URL provided: creates session, navigates, runs snapshot, returns all three:
```json
{
  "session": "1",
  "url": "https://example.com",
  "status": 200,
  "snapshot": "[1] link \"Home\"\n[2] textbox \"Search\"..."
}
```

Implementation: the `/sessions` POST endpoint accepts optional `url` field. If present, after creating the session it calls navigate + snapshot logic internally (no HTTP round-trips).

### 1.4 Tool Definition Changes

**After (6 tools):**
```
brow_session_new(url?, headed?, profile?)     — gains url, returns snapshot
brow_snapshot(session, search?)               — unchanged, for re-reads and filtering
brow_click(session, ref?, selector?)          — ref preferred, returns snapshot
brow_fill(session, ref?, selector?, value)    — ref preferred, returns snapshot
brow_select(session, ref?, selector?, value)  — ref preferred, returns snapshot
submit_answer(answer)
```

`brow_navigate` remains available for mid-task navigation but is no longer needed for the common open-and-read pattern.

**Updated system prompt:**
```
You have access to brow CLI tools for browser automation.
Use brow_session_new with a url to start a session and get the initial page snapshot.
Snapshots show numbered refs like [1], [2] for interactive elements.
Use ref= to click, fill, or select elements (e.g. brow_click ref=3).
Each action returns an updated snapshot — no need to call brow_snapshot after every action.
Use brow_snapshot with search="pattern" to filter large pages.
When done, call submit_answer with your structured result.

Example workflow:
  brow_session_new(url="https://shop.com") → snapshot shows [1] search box, [2] cart...
  brow_fill(ref=1, value="headphones") → snapshot shows [3] "Sony WH-1000" [4] "AirPods Max"...
  brow_click(ref=3) → snapshot shows product details...
  submit_answer({name: "Sony WH-1000XM5", price: "$348"})
```

### 1.5 Expected Impact

| Task | Before (calls) | After (calls) | Before (tokens) | Est. After |
|------|:-:|:-:|:-:|:-:|
| info-lookup | 6 | 3 | 16,612 | ~6,000 |
| multi-page-nav | 8 | 4 | 23,543 | ~9,000 |
| form-fill | 11 | 7 | 33,028 | ~16,000 |
| rapid-multi-step | 13 | 8 | 99,919 | ~35,000 |
| ecommerce-search | 6 | 3 | 19,206 | ~15,000 |

---

## Phase 2: Smart Snapshots

### 2.1 Table-Aware Output

Detect `<table>` elements and emit compact markdown:
```
| Name | Price | Rating |
| Roborock S7 | 12,990 CZK | 4.8 |
| Dreame L20 | 15,490 CZK | 4.6 |
... (47 more rows)
```

Tables count as 1 node toward the cap. Rows beyond 10 get dedup treatment (show first 10, emit count).

### 2.2 List Compression

When a container has >5 same-type children that are simple (single text, no deep nesting), compress to inline:
```
navigation: [1] "Home" | [2] "About" | [3] "Products" | [4] "Blog" | [5] "Contact" | [6] "Help"
```

One line instead of six. Refs preserved.

### 2.3 Adaptive Node Cap

Scale based on interactive element density:
- <50 interactive elements: cap at 200 (simple page, less structural noise)
- 50-150 interactive: cap at 400 (moderate, need room for refs)
- >150 interactive: cap at 300 but prioritize interactive elements (ensure all interactive get refs, prune non-interactive containers first)

---

## Phase 3: Agent Loop + Hard Tasks

### 3.1 Semantic Compression

Tag-based compression replacing character-length heuristic:
- **confirmation** (fill, select, key results): compress immediately to one line
- **navigation** (session_new, navigate, click responses): compress after 2 turns
- **data** (snapshot with search results): keep longer (500 char threshold)

### 3.2 Parallel Tool Execution

When the LLM issues multiple tool_use blocks in one turn, execute concurrently with `asyncio.gather()`.

### 3.3 New Benchmark Tasks

| Task ID | Category | Description |
|---------|----------|-------------|
| `deep-wizard` | throughput | 10-step form wizard with back/forward. Tests context accumulation and ref stability across step transitions. |
| `data-table-extract` | extraction | 100-row, 6-column table. Extract rows matching criteria. Tests table-aware compression. |
| `spa-navigation` | navigation | JS-driven SPA with 4 views. Tests snapshot of dynamically rendered content without full page loads. |
| `multi-tab-workflow` | interaction | Open product in new tab, compare with original, submit from both. Tests page management and per-page ref scoping. |
| `infinite-scroll` | extraction | Page loads 10 items on scroll. Find item #35. Tests scroll + repeated snapshot + search param. |
| `form-validation-recovery` | resilience | Form with server-side validation errors. First submit fails, agent must read error, fix, resubmit. |

---

## Files Changed

### Phase 1
- `brow/src/brow/routes/browser.py` — ref injection in JS, auto-snapshot in click/fill/select/navigate, ref resolution
- `brow/src/brow/routes/sessions.py` — optional url param on session create
- `brow/src/brow/snapshot.py` — format refs inline `[N] role "name"`
- `brow/src/brow/cli.py` — `--url` flag on `session new`, `--ref` flag on click/fill/select
- `benchmarks/harness/tools_brow.py` — updated tool definitions with ref support, parse auto-snapshot responses
- `benchmarks/harness/agent.py` — updated system prompt and instructions

### Phase 2
- `brow/src/brow/routes/browser.py` — table detection in JS, list compression, adaptive cap
- `brow/src/brow/snapshot.py` — markdown table formatting

### Phase 3
- `benchmarks/harness/agent.py` — semantic compression, parallel execution
- `benchmarks/fixtures/` — 6 new HTML fixture files
- `benchmarks/tasks/` — 6 new YAML task definitions
