# Phase 2: Smart Snapshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce token consumption on large/repetitive pages by making snapshots smarter — table-aware output, list compression, and adaptive node caps.

**Architecture:** Three independent compression features layered into the existing snapshot pipeline. Table detection and list compression happen in the JS `buildTree()` function (browser-side), emitting special node types. `format_tree()` in Python renders them compactly. Adaptive node cap adjusts `NODE_LIMIT` based on a pre-scan of interactive element density.

**Tech Stack:** JavaScript (Playwright `page.evaluate`), Python (FastAPI routes, snapshot formatter), pytest + pytest-asyncio

---

### File Structure

| File | Responsibility | Changes |
|------|---------------|---------|
| `brow/src/brow/routes/browser.py` | JS tree builder (`SNAPSHOT_JS`) | Table detection, list node type, adaptive cap pre-scan |
| `brow/src/brow/snapshot.py` | Python tree formatter | Markdown table rendering, inline list rendering |
| `brow/tests/test_snapshot.py` | Unit tests for formatter | New tests for table + list formatting |
| `brow/tests/test_routes_browser.py` | Integration tests | New tests for table/list/adaptive cap via real browser |

---

### Task 1: Table-Aware Snapshot Output (JS side)

**Files:**
- Modify: `brow/src/brow/routes/browser.py:48-133` (SNAPSHOT_JS buildTree function)
- Test: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write the failing integration test**

Add to `brow/tests/test_routes_browser.py`:

```python
@pytest.mark.asyncio
async def test_snapshot_table_compact(client, session_id):
    html = """data:text/html,<body><table>
        <thead><tr><th>Name</th><th>Price</th></tr></thead>
        <tbody>
            <tr><td>Widget A</td><td>$10</td></tr>
            <tr><td>Widget B</td><td>$20</td></tr>
            <tr><td>Widget C</td><td>$30</td></tr>
        </tbody>
    </table></body>"""
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    # Should contain markdown-style table, not nested role tree
    assert "| Name | Price |" in tree
    assert "Widget A" in tree
    assert "Widget C" in tree
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_snapshot_table_compact -v`
Expected: FAIL — current output uses nested `tr`/`td` roles instead of markdown table

- [ ] **Step 3: Add table detection to SNAPSHOT_JS buildTree**

In `brow/src/brow/routes/browser.py`, replace the table handling inside `buildTree`. When the function encounters a `<table>` element, instead of recursing normally, it extracts headers from `<th>` elements and rows from `<td>` elements, returning a special `{role: "table", headers: [...], rows: [[...], ...], totalRows: N}` node.

Replace the `buildTree` function body's table handling by adding this block right after the `if (SKIP.has(tag)) return null;` check:

```javascript
        // Table-aware: emit compact table node instead of deep tree
        if (tag === 'table') {
            nodeCount++;
            const headers = [];
            const rows = [];
            const ths = node.querySelectorAll('thead th, thead td, tr:first-child th');
            ths.forEach(th => headers.push(th.textContent?.trim()?.substring(0, 60) || ''));
            const trs = node.querySelectorAll('tbody tr, tr');
            const startIdx = headers.length > 0 && trs.length > 0 && trs[0].querySelector('th') ? 1 : 0;
            const MAX_TABLE_ROWS = 10;
            for (let i = startIdx; i < trs.length && rows.length < MAX_TABLE_ROWS; i++) {
                const cells = [];
                trs[i].querySelectorAll('td, th').forEach(td => {
                    cells.push(td.textContent?.trim()?.substring(0, 60) || '');
                });
                if (cells.length > 0) rows.push(cells);
            }
            const totalRows = trs.length - startIdx;
            return { role: 'table', headers, rows, totalRows };
        }
```

- [ ] **Step 4: Run test to verify it still fails (JS emits table node, but Python doesn't format it yet)**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_snapshot_table_compact -v`
Expected: FAIL — `format_tree` doesn't know about the `table` role with `headers`/`rows` keys yet

- [ ] **Step 5: Commit JS-side table detection**

```bash
git add brow/src/brow/routes/browser.py brow/tests/test_routes_browser.py
git commit -m "feat(snapshot): add table detection in JS buildTree"
```

---

### Task 2: Table-Aware Snapshot Output (Python formatter)

**Files:**
- Modify: `brow/src/brow/snapshot.py:3-32` (format_tree function)
- Test: `brow/tests/test_snapshot.py`

- [ ] **Step 1: Write the failing unit test**

Add to `brow/tests/test_snapshot.py`:

```python
def test_format_tree_table():
    tree = {
        "role": "table",
        "headers": ["Name", "Price", "Rating"],
        "rows": [
            ["Widget A", "$10", "4.5"],
            ["Widget B", "$20", "4.8"],
            ["Widget C", "$30", "4.2"],
        ],
        "totalRows": 3,
    }
    result = format_tree(tree)
    assert "| Name | Price | Rating |" in result
    assert "| Widget A | $10 | 4.5 |" in result
    assert "| Widget C | $30 | 4.2 |" in result


def test_format_tree_table_truncated():
    tree = {
        "role": "table",
        "headers": ["Name", "Price"],
        "rows": [["Item " + str(i), "$" + str(i)] for i in range(10)],
        "totalRows": 50,
    }
    result = format_tree(tree)
    assert "| Name | Price |" in result
    assert "40 more rows" in result


def test_format_tree_table_no_headers():
    tree = {
        "role": "table",
        "headers": [],
        "rows": [["A", "B"], ["C", "D"]],
        "totalRows": 2,
    }
    result = format_tree(tree)
    assert "A" in result
    assert "C" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd brow && python -m pytest tests/test_snapshot.py::test_format_tree_table -v`
Expected: FAIL — format_tree treats table node like any other role

- [ ] **Step 3: Add table rendering to format_tree**

In `brow/src/brow/snapshot.py`, add a table check at the top of `format_tree`, before the group check:

```python
def format_tree(tree, indent=0):
    if not tree:
        return ""

    role = tree.get("role", "")

    # Table-aware: render as markdown table
    if role == "table" and "headers" in tree:
        return _format_table(tree, indent)

    lines = []
    name = tree.get("name", "")
    children = tree.get("children", [])
    # ... rest unchanged
```

Add the `_format_table` helper function:

```python
def _format_table(tree, indent=0):
    prefix = "  " * indent
    headers = tree.get("headers", [])
    rows = tree.get("rows", [])
    total = tree.get("totalRows", len(rows))
    lines = []

    if headers:
        lines.append(prefix + "| " + " | ".join(headers) + " |")
        lines.append(prefix + "| " + " | ".join("---" for _ in headers) + " |")

    for row in rows:
        lines.append(prefix + "| " + " | ".join(row) + " |")

    if total > len(rows):
        lines.append(prefix + f"... ({total - len(rows)} more rows)")

    return "\n".join(lines)
```

- [ ] **Step 4: Run all snapshot tests to verify they pass**

Run: `cd brow && python -m pytest tests/test_snapshot.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run the integration test from Task 1 to verify end-to-end**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_snapshot_table_compact -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add brow/src/brow/snapshot.py brow/tests/test_snapshot.py
git commit -m "feat(snapshot): render tables as compact markdown"
```

---

### Task 3: List Compression (JS side)

**Files:**
- Modify: `brow/src/brow/routes/browser.py:48-133` (SNAPSHOT_JS buildTree function)
- Test: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write the failing integration test**

Add to `brow/tests/test_routes_browser.py`:

```python
@pytest.mark.asyncio
async def test_snapshot_list_compression(client, session_id):
    html = """data:text/html,<body><nav>
        <a href="/home">Home</a>
        <a href="/about">About</a>
        <a href="/products">Products</a>
        <a href="/blog">Blog</a>
        <a href="/contact">Contact</a>
        <a href="/help">Help</a>
        <a href="/faq">FAQ</a>
    </nav></body>"""
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    # With >5 simple same-type children, should compress to inline
    # Check that refs are still present
    assert "[1]" in tree
    assert "[7]" in tree
    # Should be inline format with pipe separators, not one-per-line indented
    lines = [l for l in tree.strip().split("\n") if "Home" in l or "FAQ" in l]
    # Both Home and FAQ should be on the same line (inline list)
    assert len(lines) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_snapshot_list_compression -v`
Expected: FAIL — each link renders on its own indented line

- [ ] **Step 3: Add list detection to SNAPSHOT_JS buildTree**

In `brow/src/brow/routes/browser.py`, after the children are built inside `buildTree`, add a check: if the node has >5 children that are all the same role and are "simple" (no nested children), emit a `{role: "inline-list", items: [...]}` node instead.

Add this logic right before the `return obj;` at the end of `buildTree`, after children are assigned to `obj.children`:

```javascript
            // List compression: inline >5 same-type simple children
            if (children.length > 5) {
                const roles = children.map(c => c.role);
                const firstRole = roles[0];
                const allSame = roles.every(r => r === firstRole);
                const allSimple = children.every(c => !c.children);
                if (allSame && allSimple) {
                    return { role: 'inline-list', itemRole: firstRole, items: children };
                }
            }
```

- [ ] **Step 4: Run test — will still fail because Python doesn't render inline-list yet**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_snapshot_list_compression -v`
Expected: FAIL

- [ ] **Step 5: Commit JS-side list detection**

```bash
git add brow/src/brow/routes/browser.py brow/tests/test_routes_browser.py
git commit -m "feat(snapshot): detect compressible lists in JS buildTree"
```

---

### Task 4: List Compression (Python formatter)

**Files:**
- Modify: `brow/src/brow/snapshot.py` (format_tree function)
- Test: `brow/tests/test_snapshot.py`

- [ ] **Step 1: Write the failing unit test**

Add to `brow/tests/test_snapshot.py`:

```python
def test_format_tree_inline_list():
    tree = {
        "role": "inline-list",
        "itemRole": "link",
        "items": [
            {"role": "link", "name": "Home", "href": "/", "ref": 1},
            {"role": "link", "name": "About", "href": "/about", "ref": 2},
            {"role": "link", "name": "Products", "href": "/products", "ref": 3},
            {"role": "link", "name": "Blog", "href": "/blog", "ref": 4},
            {"role": "link", "name": "Contact", "href": "/contact", "ref": 5},
            {"role": "link", "name": "Help", "href": "/help", "ref": 6},
        ],
    }
    result = format_tree(tree)
    # Should be one line with pipe separators and refs preserved
    assert "[1]" in result
    assert "[6]" in result
    assert "|" in result
    lines = result.strip().split("\n")
    assert len(lines) == 1


def test_format_tree_inline_list_no_refs():
    tree = {
        "role": "inline-list",
        "itemRole": "li",
        "items": [
            {"role": "li", "name": "Item A"},
            {"role": "li", "name": "Item B"},
            {"role": "li", "name": "Item C"},
            {"role": "li", "name": "Item D"},
            {"role": "li", "name": "Item E"},
            {"role": "li", "name": "Item F"},
        ],
    }
    result = format_tree(tree)
    assert "Item A" in result
    assert "Item F" in result
    assert "|" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd brow && python -m pytest tests/test_snapshot.py::test_format_tree_inline_list -v`
Expected: FAIL

- [ ] **Step 3: Add inline-list rendering to format_tree**

In `brow/src/brow/snapshot.py`, add an inline-list check after the table check:

```python
    # Inline list: render same-type simple children on one line
    if role == "inline-list" and "items" in tree:
        return _format_inline_list(tree, indent)
```

Add the helper function:

```python
def _format_inline_list(tree, indent=0):
    prefix = "  " * indent
    parts = []
    for item in tree.get("items", []):
        ref = item.get("ref")
        name = item.get("name", "")
        piece = f'[{ref}] "{name}"' if ref is not None else f'"{name}"'
        parts.append(piece)
    item_role = tree.get("itemRole", "item")
    return prefix + item_role + ": " + " | ".join(parts)
```

- [ ] **Step 4: Run all snapshot tests**

Run: `cd brow && python -m pytest tests/test_snapshot.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run the integration test from Task 3**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_snapshot_list_compression -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add brow/src/brow/snapshot.py brow/tests/test_snapshot.py
git commit -m "feat(snapshot): render inline lists with pipe separators"
```

---

### Task 5: Adaptive Node Cap

**Files:**
- Modify: `brow/src/brow/routes/browser.py:13-133` (SNAPSHOT_JS)
- Test: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write the failing integration test**

Add to `brow/tests/test_routes_browser.py`:

```python
@pytest.mark.asyncio
async def test_adaptive_cap_simple_page(client, session_id):
    """Simple page with few interactive elements gets lower node cap (200)."""
    html = "data:text/html,<body><h1>Title</h1><p>Paragraph</p><a href='/'>Link</a></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    # Just verify it works — the real test is that large non-interactive pages get capped sooner
    assert "Title" in r.json()["tree"]


@pytest.mark.asyncio
async def test_adaptive_cap_many_interactive(client, session_id):
    """Page with many interactive elements gets higher cap and prioritizes them."""
    buttons = "".join(f'<button>Btn {i}</button>' for i in range(60))
    paragraphs = "".join(f'<p>Filler paragraph {i}</p>' for i in range(200))
    html = f"data:text/html,<body>{buttons}{paragraphs}</body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    # All 60 buttons should have refs (interactive elements prioritized)
    assert "[60]" in tree
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd brow && python -m pytest tests/test_routes_browser.py::test_adaptive_cap_many_interactive -v`
Expected: FAIL — with fixed NODE_LIMIT=300, the 200 filler paragraphs may prevent all 60 buttons from getting refs

- [ ] **Step 3: Add adaptive cap pre-scan to SNAPSHOT_JS**

In `brow/src/brow/routes/browser.py`, modify `SNAPSHOT_JS` to add a pre-scan that counts interactive elements before building the tree, then sets `NODE_LIMIT` accordingly:

Replace the lines:
```javascript
    let nodeCount = 0;
    let refCounter = 0;
    const NODE_LIMIT = 300;
```

With:
```javascript
    // Pre-scan: count interactive elements to set adaptive cap
    const allElements = document.body.querySelectorAll('*');
    let interactiveCount = 0;
    for (const el of allElements) {
        const t = el.tagName.toLowerCase();
        if (INTERACTIVE.has(t) || INTERACTIVE_ROLES.has(el.getAttribute('role'))) {
            interactiveCount++;
        }
    }

    let NODE_LIMIT;
    if (interactiveCount < 50) {
        NODE_LIMIT = 200;
    } else if (interactiveCount <= 150) {
        NODE_LIMIT = 400;
    } else {
        NODE_LIMIT = 300;  // Prioritize interactive, prune non-interactive
    }

    let nodeCount = 0;
    let refCounter = 0;
    const skipNonInteractive = interactiveCount > 150;
```

Then, in the `buildTree` function, after the `if (!isInteractive && !isSemantic && !name)` block, add priority pruning. Replace:

```javascript
        if (!isInteractive && !isSemantic && !name) {
            if (children.length === 0) return null;
            if (children.length === 1) return children[0];
            return { role: 'group', children };
        }
```

With:

```javascript
        if (!isInteractive && !isSemantic && !name) {
            if (children.length === 0) return null;
            if (children.length === 1) return children[0];
            return { role: 'group', children };
        }

        // When interactive-dense, skip non-interactive non-semantic nodes sooner
        if (skipNonInteractive && !isInteractive && nodeCount > NODE_LIMIT * 0.7) {
            if (children.length === 0) return null;
            return { role: 'group', children };
        }
```

Also add `interactiveCount` to the return value:

```javascript
    const tree = buildTree(document.body, 0);
    return { tree, truncated: nodeCount >= NODE_LIMIT, nodeCount, refCount: refCounter, interactiveCount };
```

- [ ] **Step 4: Run all browser route tests**

Run: `cd brow && python -m pytest tests/test_routes_browser.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add brow/src/brow/routes/browser.py brow/tests/test_routes_browser.py
git commit -m "feat(snapshot): adaptive node cap based on interactive density"
```

---

### Task 6: Run All Tests and Verify

**Files:**
- Verify: `brow/tests/test_snapshot.py`, `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Run full brow test suite**

Run: `cd brow && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run benchmark integration tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest benchmarks/tests/ -v`
Expected: ALL PASS (or skip if no fixture server)

- [ ] **Step 3: Commit any fixes needed**

Only if tests revealed issues — fix and commit with descriptive message.

---

### Task 7: Run Benchmarks and Compare

**Files:**
- Output: `benchmarks/results_v3/` (brow v3 results)
- Modify: `benchmarks/README.md`

- [ ] **Step 1: Run brow v3 benchmarks on 10 original tasks**

```bash
cd /Users/danherma/projects-personal/brow
python -m benchmarks.run --backend brow --runs 1 --output benchmarks/results_v3/
```

- [ ] **Step 2: Compare v2 vs v3 results**

Read `benchmarks/results_v3/report.md` and compare against `benchmarks/results_v2/report.md`.

Key metrics to compare:
- Average tokens/task (target: reduce from 54,647)
- login-auth tokens (target: reduce from 137,351)
- rapid-multi-step tokens (target: reduce from 114,508)
- large-snapshot tokens (target: reduce from 225,821)
- Success rate (target: maintain or improve 60%)

- [ ] **Step 3: Update README with v3 results**

Update `benchmarks/README.md` with the new results table, adding a v2 vs v3 comparison.

- [ ] **Step 4: Commit results and README**

```bash
git add benchmarks/results_v3/ benchmarks/README.md
git commit -m "docs(bench): add Phase 2 (smart snapshots) benchmark results"
```

---

## Self-Review

**Spec coverage check:**
- 2.1 Table-aware output: Tasks 1 + 2 (JS detection + Python rendering)
- 2.2 List compression: Tasks 3 + 4 (JS detection + Python rendering)
- 2.3 Adaptive node cap: Task 5
- Benchmarking: Task 7

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" references. All code blocks are complete.

**Type consistency:**
- `_format_table(tree, indent)` — used consistently in Tasks 1+2
- `_format_inline_list(tree, indent)` — used consistently in Tasks 3+4
- `role: "table"` with `headers`, `rows`, `totalRows` keys — consistent between JS (Task 1) and Python (Task 2)
- `role: "inline-list"` with `itemRole`, `items` keys — consistent between JS (Task 3) and Python (Task 4)
