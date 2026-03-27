# Brow Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce brow's token consumption and tool call count to match or beat playwright-cli across all benchmark tasks by adding ref-based element addressing, auto-snapshot after actions, combined session+navigate, and new harder benchmark tasks.

**Architecture:** Three layers of change — (1) brow daemon API gains ref injection in snapshots and auto-snapshot responses on mutation endpoints, (2) CLI and client pass through new params, (3) benchmark tool definitions and agent prompt updated to use refs. New fixture tasks stress-test the improvements.

**Tech Stack:** Python 3.13, FastAPI, Playwright, Typer CLI, pytest, httpx

---

## File Structure

### Modified files
| File | Change |
|------|--------|
| `brow/src/brow/routes/browser.py` | Ref injection in JS, auto-snapshot on click/fill/navigate/key/select, ref resolution helper, new select endpoint |
| `brow/src/brow/routes/sessions.py` | Optional `url` field on session create → navigate+snapshot |
| `brow/src/brow/snapshot.py` | Format refs inline as `[N]` prefix |
| `brow/src/brow/cli.py` | `--url` on `session new`, `--ref` on click/fill, new `select` command |
| `brow/src/brow/client.py` | No changes needed (generic HTTP client) |
| `benchmarks/harness/tools_brow.py` | Ref-based tool definitions, updated cmd builders |
| `benchmarks/harness/agent.py` | Updated system prompt with ref workflow |
| `benchmarks/fixtures/app.py` | New fixture routes for 6 tasks |

### New files
| File | Purpose |
|------|---------|
| `benchmarks/fixtures/static/deep-wizard.html` | 10-step wizard fixture |
| `benchmarks/fixtures/static/data-table.html` | 100-row table fixture |
| `benchmarks/fixtures/static/spa/index.html` | SPA with JS routing fixture |
| `benchmarks/fixtures/static/products.html` | Multi-tab product comparison fixture |
| `benchmarks/fixtures/static/infinite-scroll.html` | Infinite scroll fixture |
| `benchmarks/fixtures/static/validation-form.html` | Form with validation errors fixture |
| `benchmarks/tasks/deep-wizard.yaml` | Task definition |
| `benchmarks/tasks/data-table-extract.yaml` | Task definition |
| `benchmarks/tasks/spa-navigation.yaml` | Task definition |
| `benchmarks/tasks/multi-tab-workflow.yaml` | Task definition |
| `benchmarks/tasks/infinite-scroll.yaml` | Task definition |
| `benchmarks/tasks/form-validation-recovery.yaml` | Task definition |

### Test files
| File | Tests |
|------|-------|
| `brow/tests/test_routes_browser.py` | Ref injection, auto-snapshot, ref-based click/fill, select endpoint |
| `brow/tests/test_routes_sessions.py` | Session create with url |
| `brow/tests/test_snapshot.py` | Ref formatting in output |

---

### Task 1: Ref Injection in Snapshot JS

**Files:**
- Modify: `brow/src/brow/routes/browser.py:109-217`
- Modify: `brow/src/brow/snapshot.py:3-28`
- Test: `brow/tests/test_snapshot.py`
- Test: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write failing test for ref in snapshot output**

In `brow/tests/test_snapshot.py`, add:

```python
def test_format_tree_with_ref():
    tree = {
        "role": "heading", "name": "Title", "level": 1,
    }
    result = format_tree(tree)
    assert "heading" in result
    # No ref on non-interactive
    assert "[" not in result

    interactive_tree = {
        "role": "button", "name": "Submit", "ref": 1,
    }
    result = format_tree(interactive_tree)
    assert "[1]" in result
    assert 'button "Submit"' in result


def test_format_tree_multiple_refs():
    tree = {
        "role": "WebArea",
        "name": "Page",
        "children": [
            {"role": "link", "name": "Home", "href": "/", "ref": 1},
            {"role": "heading", "name": "Welcome", "level": 1},
            {"role": "textbox", "name": "Email", "ref": 2},
            {"role": "button", "name": "Submit", "ref": 3},
        ],
    }
    result = format_tree(tree)
    lines = result.strip().split("\n")
    # link should have [1], heading no ref, textbox [2], button [3]
    assert "[1]" in lines[1]
    assert "[" not in lines[2]  # heading
    assert "[2]" in lines[3]
    assert "[3]" in lines[4]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_snapshot.py::test_format_tree_with_ref brow/tests/test_snapshot.py::test_format_tree_multiple_refs -v`

Expected: FAIL — `[1]` not in output

- [ ] **Step 3: Update `format_tree` to render refs**

In `brow/src/brow/snapshot.py`, update `format_tree`:

```python
import re

def format_tree(tree, indent=0):
    if not tree:
        return ""
    lines = []
    role = tree.get("role", "")
    name = tree.get("name", "")
    ref = tree.get("ref")
    children = tree.get("children", [])

    if role == "group" and not name and not ref:
        for child in children:
            lines.append(format_tree(child, indent))
        return "\n".join(lines)

    parts = []
    if ref is not None:
        parts.append(f"[{ref}]")
    parts.append(role)
    if name:
        parts.append(f'"{name}"')
    for key in ("value", "checked", "disabled", "href", "level"):
        if key in tree:
            v = tree[key]
            parts.append(f"{key}={v}" if not isinstance(v, str) else f'{key}="{v}"')

    prefix = "  " * indent
    lines.append(f"{prefix}{' '.join(parts)}")
    for child in children:
        lines.append(format_tree(child, indent + 1))
    return "\n".join(lines)


def filter_lines(text, pattern, limit=10):
    regex = re.compile(pattern)
    matches = [l for l in text.split("\n") if regex.search(l)]
    return "\n".join(matches[:limit])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_snapshot.py -v`

Expected: All tests PASS

- [ ] **Step 5: Write failing test for ref injection in snapshot endpoint**

In `brow/tests/test_routes_browser.py`, add:

```python
@pytest.mark.asyncio
async def test_snapshot_has_refs(client, session_id):
    html = "data:text/html,<body><a href='/'>Home</a><h1>Title</h1><button>Click</button></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.get(f"/browser/{session_id}/snapshot")
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert "[1]" in tree  # link gets ref 1
    assert "[2]" in tree  # button gets ref 2
    # heading should NOT have a ref
    lines = tree.strip().split("\n")
    heading_line = [l for l in lines if "Title" in l][0]
    assert "[" not in heading_line
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_snapshot_has_refs -v`

Expected: FAIL — `[1]` not in tree output

- [ ] **Step 7: Add ref injection to snapshot JS in `browser.py`**

In `brow/src/brow/routes/browser.py`, update the JS code in the `snapshot` function. Add ref counter and `data-brow-ref` attribute injection. The key changes to `buildTree`:

1. Add `let refCounter = 0;` before `buildTree`
2. Add a set of interactive roles: `const INTERACTIVE_ROLES = new Set(['button','tab','link','menuitem','option','switch','checkbox','radio','slider','spinbutton','combobox','searchbox','textbox']);`
3. Before building the node object for interactive elements, inject a `data-brow-ref` and include `ref` in the returned object
4. Add a cleanup pass at the top: `document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));`

Replace the full JS code block (lines 109-217) with:

```python
    js_code = """
    () => {
        // Clean up any previous refs
        document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));

        const INTERACTIVE = new Set([
            'a', 'button', 'input', 'select', 'textarea', 'option',
            'details', 'summary', 'dialog', 'menu', 'menuitem',
        ]);
        const INTERACTIVE_ROLES = new Set([
            'button','tab','link','menuitem','option','switch',
            'checkbox','radio','slider','spinbutton','combobox',
            'searchbox','textbox',
        ]);
        const SEMANTIC = new Set([
            'h1','h2','h3','h4','h5','h6','img','video','audio',
            'table','thead','tbody','tr','th','td','ul','ol','li',
            'form','label','fieldset','legend','nav','main',
        ]);
        const SKIP = new Set([
            'script','style','noscript','svg','path','link','meta',
            'br','hr','iframe',
        ]);

        let nodeCount = 0;
        const NODE_LIMIT = 300;
        let refCounter = 0;

        function sig(node) {
            if (node.nodeType !== Node.ELEMENT_NODE) return '';
            const tag = node.tagName;
            const cls = node.className ? '.' + node.className.split(' ')[0] : '';
            const ch = node.children.length;
            return tag + cls + ch;
        }

        function buildTree(node, depth) {
            if (!node || depth > 15 || nodeCount >= NODE_LIMIT) return null;

            if (node.nodeType === Node.TEXT_NODE) {
                const t = node.textContent?.trim();
                if (!t || !t.length) return null;
                nodeCount++;
                return { role: 'text', name: t.substring(0, 80) };
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return null;

            const tag = node.tagName.toLowerCase();
            if (SKIP.has(tag)) return null;
            if (node.hidden || node.getAttribute('aria-hidden') === 'true') return null;

            const role = node.getAttribute('role') || tag;
            const ariaLabel = node.getAttribute('aria-label');
            const alt = node.getAttribute('alt');
            const placeholder = node.getAttribute('placeholder');
            const name = ariaLabel || alt || node.getAttribute('title') || '';
            const isInteractive = INTERACTIVE.has(tag) || INTERACTIVE_ROLES.has(node.getAttribute('role'));
            const isSemantic = SEMANTIC.has(tag);

            const childNodes = Array.from(node.childNodes);
            let children = [];
            let lastSig = '', repeatCount = 0;
            for (const child of childNodes) {
                if (nodeCount >= NODE_LIMIT) break;
                const s = sig(child);
                if (s && s === lastSig) {
                    repeatCount++;
                    if (repeatCount > 3) continue;
                } else {
                    if (repeatCount > 3) {
                        children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
                        nodeCount++;
                    }
                    lastSig = s;
                    repeatCount = 0;
                }
                const c = buildTree(child, depth + 1);
                if (c) children.push(c);
            }
            if (repeatCount > 3) {
                children.push({ role: 'text', name: '... ' + (repeatCount - 3) + ' similar items omitted' });
                nodeCount++;
            }

            if (!isInteractive && !isSemantic && !name) {
                if (children.length === 0) return null;
                if (children.length === 1) return children[0];
                return { role: 'group', children };
            }

            nodeCount++;
            const obj = { role };

            // Assign ref to interactive elements
            if (isInteractive) {
                refCounter++;
                node.setAttribute('data-brow-ref', String(refCounter));
                obj.ref = refCounter;
            }

            if (name) obj.name = name.substring(0, 80);
            else if (isInteractive && !name) {
                const txt = node.textContent?.trim()?.substring(0, 50);
                if (txt) obj.name = txt;
            }
            if (placeholder && !obj.name) obj.name = placeholder;
            if (node.value !== undefined && node.value !== '') obj.value = String(node.value).substring(0, 80);
            if (node.checked !== undefined) obj.checked = node.checked;
            if (node.disabled) obj.disabled = true;
            if (tag === 'a' && node.href) obj.href = node.href;

            if (children.length > 0) {
                if (children.length === 1 && children[0].role === 'text' && !obj.name) {
                    obj.name = children[0].name;
                } else {
                    obj.children = children;
                }
            }

            return obj;
        }

        const tree = buildTree(document.body, 0);
        return { tree, truncated: nodeCount >= NODE_LIMIT, nodeCount, refCount: refCounter };
    }
    """
```

- [ ] **Step 8: Run all snapshot tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_snapshot_has_refs brow/tests/test_routes_browser.py::test_snapshot brow/tests/test_snapshot.py -v`

Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add brow/src/brow/routes/browser.py brow/src/brow/snapshot.py brow/tests/test_snapshot.py brow/tests/test_routes_browser.py
git commit -m "feat: add ref injection to snapshot — interactive elements get numbered [N] refs"
```

---

### Task 2: Ref-Based Click and Fill

**Files:**
- Modify: `brow/src/brow/routes/browser.py:34-36,289-341`
- Test: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write failing test for ref-based click**

In `brow/tests/test_routes_browser.py`, add:

```python
@pytest.mark.asyncio
async def test_click_by_ref(client, session_id):
    html = "data:text/html,<body><button id='btn' onclick='document.title=\"clicked\"'>Click</button></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    # First snapshot to inject refs
    await client.get(f"/browser/{session_id}/snapshot")
    # Click by ref
    r = await client.post(f"/browser/{session_id}/click", json={"ref": 1})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_fill_by_ref(client, session_id):
    html = "data:text/html,<body><input id='inp' type='text'/></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.get(f"/browser/{session_id}/snapshot")
    r = await client.post(f"/browser/{session_id}/fill", json={"ref": 1, "value": "hello"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_click_by_ref brow/tests/test_routes_browser.py::test_fill_by_ref -v`

Expected: FAIL — validation error, `ref` not in schema

- [ ] **Step 3: Update ClickReq and FillReq to accept optional ref**

In `brow/src/brow/routes/browser.py`, update the request models:

```python
class ClickReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    timeout: int = DEFAULT_TIMEOUT
    retry: int = 0
    wait_for_selector: bool = True

class FillReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    value: str
    timeout: int = DEFAULT_TIMEOUT
    retry: int = 0
    wait_for_selector: bool = True
```

- [ ] **Step 4: Add ref resolution helper**

In `brow/src/brow/routes/browser.py`, add after `_get_page`:

```python
def _resolve_selector(body):
    """Resolve ref to CSS selector, or use selector directly."""
    if hasattr(body, 'ref') and body.ref is not None:
        return f'[data-brow-ref="{body.ref}"]'
    if hasattr(body, 'selector') and body.selector is not None:
        return body.selector
    raise HTTPException(400, "Either 'ref' or 'selector' must be provided")
```

- [ ] **Step 5: Update click and fill to use `_resolve_selector`**

In the `click` handler, replace `body.selector` with `_resolve_selector(body)`:

```python
@router.post("/click")
async def click(req: Request, sid: str, body: ClickReq):
    import asyncio as aio

    session = _get_session(req, sid)
    page = _get_page(session)
    selector = _resolve_selector(body)

    attempts = body.retry + 1
    last_error = None

    for attempt in range(attempts):
        try:
            if body.wait_for_selector:
                await page.wait_for_selector(selector, timeout=body.timeout, state="visible")

            await page.click(selector, timeout=body.timeout)
            return {"ok": True}
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500,
        f"Failed to click '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
    )
```

Same pattern for `fill` — replace `body.selector` with `selector = _resolve_selector(body)` and use `selector` throughout.

- [ ] **Step 6: Run tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_click_by_ref brow/tests/test_routes_browser.py::test_fill_by_ref brow/tests/test_routes_browser.py::test_click brow/tests/test_routes_browser.py::test_fill -v`

Expected: All PASS (both ref-based and selector-based)

- [ ] **Step 7: Commit**

```bash
git add brow/src/brow/routes/browser.py brow/tests/test_routes_browser.py
git commit -m "feat: click and fill accept ref= as alternative to selector="
```

---

### Task 3: Select Endpoint with Ref Support

**Files:**
- Modify: `brow/src/brow/routes/browser.py`
- Test: `brow/tests/test_routes_browser.py`

Currently `brow_select` in benchmarks uses `brow eval` with raw `page.select_option()`. Add a proper `/select` endpoint.

- [ ] **Step 1: Write failing test**

In `brow/tests/test_routes_browser.py`, add:

```python
@pytest.mark.asyncio
async def test_select(client, session_id):
    html = "data:text/html,<body><select id='sel'><option value='a'>A</option><option value='b'>B</option></select></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/select", json={"selector": "#sel", "value": "b"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_select_by_ref(client, session_id):
    html = "data:text/html,<body><select id='sel'><option value='a'>A</option><option value='b'>B</option></select></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    await client.get(f"/browser/{session_id}/snapshot")
    r = await client.post(f"/browser/{session_id}/select", json={"ref": 1, "value": "b"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_select brow/tests/test_routes_browser.py::test_select_by_ref -v`

Expected: FAIL — 404 or 405

- [ ] **Step 3: Add SelectReq model and select endpoint**

In `brow/src/brow/routes/browser.py`, add the model and endpoint:

```python
class SelectReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    value: str
    timeout: int = DEFAULT_TIMEOUT

@router.post("/select")
async def select_option(req: Request, sid: str, body: SelectReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    selector = _resolve_selector(body)
    await page.select_option(selector, body.value, timeout=body.timeout)
    return {"ok": True}
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_select brow/tests/test_routes_browser.py::test_select_by_ref -v`

Expected: PASS

- [ ] **Step 5: Add `select` CLI command**

In `brow/src/brow/cli.py`, add after the `fill_cmd`:

```python
@app.command("select")
def select_cmd(
    selector: Optional[str] = typer.Argument(None),
    value: str = typer.Argument(...),
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    s: Optional[str] = session_opt,
    timeout: int = 30000,
):
    ensure_daemon()
    c = _client()
    payload = {"value": value, "timeout": timeout}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    run_async(c.post(f"/browser/{s}/select", json=payload))
```

- [ ] **Step 6: Commit**

```bash
git add brow/src/brow/routes/browser.py brow/src/brow/cli.py brow/tests/test_routes_browser.py
git commit -m "feat: add /select endpoint with ref support"
```

---

### Task 4: Auto-Snapshot on Mutation Endpoints

**Files:**
- Modify: `brow/src/brow/routes/browser.py`
- Test: `brow/tests/test_routes_browser.py`

- [ ] **Step 1: Write failing test for auto-snapshot on click**

In `brow/tests/test_routes_browser.py`, add:

```python
@pytest.mark.asyncio
async def test_click_returns_snapshot(client, session_id):
    html = "data:text/html,<body><a href='data:text/html,<h1>Page2</h1>'>Go</a></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/click", json={"selector": "a"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "snapshot" in body
    assert "Page2" in body["snapshot"]


@pytest.mark.asyncio
async def test_fill_returns_snapshot(client, session_id):
    html = "data:text/html,<body><input id='inp' type='text'/><p>Label</p></body>"
    await client.post(f"/browser/{session_id}/navigate", json={"url": html})
    r = await client.post(f"/browser/{session_id}/fill", json={"selector": "#inp", "value": "test"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "snapshot" in body
    assert "Label" in body["snapshot"]


@pytest.mark.asyncio
async def test_navigate_returns_snapshot(client, session_id):
    r = await client.post(
        f"/browser/{session_id}/navigate",
        json={"url": "data:text/html,<body><h1>Hello</h1><button>Click</button></body>"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "snapshot" in body
    assert "Hello" in body["snapshot"]
    assert "[1]" in body["snapshot"]  # button gets a ref
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py::test_click_returns_snapshot brow/tests/test_routes_browser.py::test_fill_returns_snapshot brow/tests/test_routes_browser.py::test_navigate_returns_snapshot -v`

Expected: FAIL — `snapshot` not in response

- [ ] **Step 3: Extract snapshot logic into a reusable helper**

In `brow/src/brow/routes/browser.py`, add a helper function that runs the snapshot JS and formats the result. Place it after `_resolve_selector`:

```python
async def _take_snapshot(page, search=None):
    """Run snapshot JS on page, return formatted tree string and metadata."""
    js_code = """..."""  # Same JS as in the snapshot endpoint — extract to module-level constant
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass  # Best effort — don't fail the action if load state times out
    result = await page.evaluate(js_code)
    tree = result.get("tree") if isinstance(result, dict) else result
    truncated = result.get("truncated", False) if isinstance(result, dict) else False
    node_count = result.get("nodeCount", 0) if isinstance(result, dict) else 0
    formatted = format_tree(tree) if tree else ""
    if search:
        formatted = filter_lines(formatted, search)
    return formatted, truncated, node_count
```

Move the JS code to a module-level constant `SNAPSHOT_JS` to avoid duplication between the snapshot endpoint and the helper.

- [ ] **Step 4: Update snapshot endpoint to use `_take_snapshot`**

```python
@router.get("/snapshot")
async def snapshot(req: Request, sid: str, search: Optional[str] = None, locator: Optional[str] = None):
    session = _get_session(req, sid)
    page = _get_page(session)
    formatted, truncated, node_count = await _take_snapshot(page, search)
    resp = {"tree": formatted}
    if truncated:
        resp["truncated"] = True
        resp["hint"] = f"Page has {node_count}+ nodes. Use search param to filter, e.g. search='Item 100'"
    return resp
```

- [ ] **Step 5: Add auto-snapshot to navigate**

```python
@router.post("/navigate")
async def navigate(req: Request, sid: str, body: NavigateReq):
    import logging
    session = _get_session(req, sid)
    page = _get_page(session)
    try:
        r = await page.goto(body.url, timeout=body.timeout)
    except Exception as e:
        logging.error(f"Navigate to {body.url} failed: {e}")
        raise HTTPException(502, f"Navigation failed: {e}")
    formatted, truncated, node_count = await _take_snapshot(page)
    resp = {"url": page.url, "status": r.status if r else None, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
        resp["hint"] = f"Page has {node_count}+ nodes. Use search param to filter."
    return resp
```

- [ ] **Step 6: Add auto-snapshot to click**

After the successful `await page.click(...)`, instead of `return {"ok": True}`:

```python
            await page.click(selector, timeout=body.timeout)
            formatted, truncated, _ = await _take_snapshot(page)
            resp = {"ok": True, "snapshot": formatted}
            if truncated:
                resp["truncated"] = True
            return resp
```

- [ ] **Step 7: Add auto-snapshot to fill, select, key**

Same pattern for fill (after `await page.fill(...)`), select (after `await page.select_option(...)`), and key (after `await page.keyboard.press(...)`):

```python
formatted, truncated, _ = await _take_snapshot(page)
resp = {"ok": True, "snapshot": formatted}
if truncated:
    resp["truncated"] = True
return resp
```

- [ ] **Step 8: Run all tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_browser.py -v`

Expected: All PASS (including old tests — they may need minor updates if they check exact response shape, but old tests only check `r.json()["ok"]` or `r.json()["url"]` which are still present)

- [ ] **Step 9: Commit**

```bash
git add brow/src/brow/routes/browser.py brow/tests/test_routes_browser.py
git commit -m "feat: auto-snapshot on navigate, click, fill, select, key — actions return page state"
```

---

### Task 5: Combined Session + Navigate + Snapshot

**Files:**
- Modify: `brow/src/brow/routes/sessions.py`
- Modify: `brow/src/brow/cli.py:87-92`
- Test: `brow/tests/test_routes_sessions.py`

- [ ] **Step 1: Write failing test**

In `brow/tests/test_routes_sessions.py`, add (read the file first to see existing test patterns):

```python
@pytest.mark.asyncio
async def test_create_session_with_url(client):
    r = await client.post("/sessions", json={
        "profile": "test-url",
        "headless": True,
        "url": "data:text/html,<body><h1>Hello</h1><button>Click</button></body>"
    })
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert "snapshot" in body
    assert "Hello" in body["snapshot"]
    assert "[1]" in body["snapshot"]  # button ref
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_sessions.py::test_create_session_with_url -v`

Expected: FAIL — `snapshot` not in response

- [ ] **Step 3: Update CreateSession model and handler**

In `brow/src/brow/routes/sessions.py`:

```python
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/sessions", tags=["sessions"])

class CreateSession(BaseModel):
    profile: str = "default"
    headless: bool = True
    url: Optional[str] = None

@router.post("")
async def create(req: Request, body: CreateSession):
    mgr = req.app.state.manager
    profiles = req.app.state.profiles
    pw = req.app.state.pw
    try:
        sid = mgr.create(body.profile, body.headless)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    session = mgr.get(sid)
    user_data_dir = profiles.get_profile_dir(body.profile)
    await session.launch(pw, user_data_dir)

    resp = {"id": sid, "profile": body.profile}

    if body.url:
        page = session.page
        if page:
            from brow.routes.browser import _take_snapshot
            import logging
            try:
                r = await page.goto(body.url, timeout=30000)
                resp["url"] = page.url
                resp["status"] = r.status if r else None
            except Exception as e:
                logging.error(f"Navigate to {body.url} failed: {e}")
                resp["url"] = body.url
                resp["status"] = None
                resp["error"] = f"Navigation failed: {e}"
            formatted, truncated, node_count = await _take_snapshot(page)
            resp["snapshot"] = formatted
            if truncated:
                resp["truncated"] = True

    return resp
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/test_routes_sessions.py -v`

Expected: All PASS

- [ ] **Step 5: Update CLI `session new` with `--url`**

In `brow/src/brow/cli.py`, update `session_new`:

```python
@session_app.command("new")
def session_new(profile: str = "default", headed: bool = False, url: Optional[str] = None):
    ensure_daemon()
    c = _client()
    payload = {"profile": profile, "headless": not headed}
    if url:
        payload["url"] = url
    result = run_async(c.post("/sessions", json=payload))
    typer.echo(result["id"])
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
```

- [ ] **Step 6: Update CLI click and fill with `--ref`**

In `brow/src/brow/cli.py`, update `click_cmd`:

```python
@app.command("click")
def click_cmd(
    selector: Optional[str] = typer.Argument(None),
    s: Optional[str] = session_opt,
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    timeout: int = 30000,
    retry: int = 0,
    no_wait: bool = typer.Option(False, help="Skip waiting for selector to be visible")
):
    ensure_daemon()
    c = _client()
    payload = {"timeout": timeout, "retry": retry, "wait_for_selector": not no_wait}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = run_async(c.post(f"/browser/{s}/click", json=payload))
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
```

Same pattern for `fill_cmd`:

```python
@app.command("fill")
def fill_cmd(
    selector: Optional[str] = typer.Argument(None),
    value: str = typer.Argument(...),
    s: Optional[str] = session_opt,
    ref: Optional[int] = typer.Option(None, "--ref", help="Element ref from snapshot"),
    timeout: int = 30000,
    retry: int = 0,
    no_wait: bool = typer.Option(False, help="Skip waiting for selector to be visible")
):
    ensure_daemon()
    c = _client()
    payload = {"value": value, "timeout": timeout, "retry": retry, "wait_for_selector": not no_wait}
    if ref is not None:
        payload["ref"] = ref
    elif selector is not None:
        payload["selector"] = selector
    else:
        typer.echo("Either selector or --ref required", err=True)
        raise typer.Exit(1)
    result = run_async(c.post(f"/browser/{s}/fill", json=payload))
    if result.get("snapshot"):
        typer.echo(result["snapshot"])
```

- [ ] **Step 7: Run full test suite**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/ -v`

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add brow/src/brow/routes/sessions.py brow/src/brow/cli.py brow/tests/test_routes_sessions.py
git commit -m "feat: session new accepts --url, click/fill accept --ref — combined operations"
```

---

### Task 6: Update Benchmark Tool Definitions

**Files:**
- Modify: `benchmarks/harness/tools_brow.py`
- Modify: `benchmarks/harness/agent.py:22-27,40-54`

- [ ] **Step 1: Replace BROW_TOOLS with ref-based definitions**

In `benchmarks/harness/tools_brow.py`, replace `BROW_TOOLS`:

```python
import json
import uuid

BROW_TOOLS = [
    {
        "name": "brow_session_new",
        "description": "Start a new browser session. If url is provided, navigates to it and returns the initial snapshot with element refs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to after creating session"},
                "profile": {"type": "string", "default": "benchmark"},
                "headed": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "brow_snapshot",
        "description": "Get the accessibility tree of the current page. Use search= to filter large pages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "search": {"type": "string", "description": "Regex to filter snapshot lines"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_click",
        "description": "Click an element by ref (from snapshot) or CSS selector. Returns updated snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "ref": {"type": "integer", "description": "Element ref number from snapshot (preferred)"},
                "selector": {"type": "string", "description": "CSS selector (fallback)"},
            },
            "required": ["session"],
        },
    },
    {
        "name": "brow_fill",
        "description": "Fill an input field by ref or selector. Returns updated snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "ref": {"type": "integer", "description": "Element ref number from snapshot (preferred)"},
                "selector": {"type": "string", "description": "CSS selector (fallback)"},
                "value": {"type": "string"},
            },
            "required": ["session", "value"],
        },
    },
    {
        "name": "brow_select",
        "description": "Select an option from a dropdown by ref or selector. Returns updated snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "ref": {"type": "integer", "description": "Element ref number from snapshot (preferred)"},
                "selector": {"type": "string", "description": "CSS selector (fallback)"},
                "value": {"type": "string"},
            },
            "required": ["session", "value"],
        },
    },
    {
        "name": "brow_scroll",
        "description": "Scroll the page by pixels or to a selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {"type": "string"},
                "pixels": {"type": "integer"},
                "selector": {"type": "string"},
            },
            "required": ["session"],
        },
    },
]
```

- [ ] **Step 2: Update `_build_brow_cmd` for new tool shapes**

```python
def _build_brow_cmd(name, params):
    def _cmd(subcmd, p, *args):
        return ["brow", subcmd, "-s", p["session"]] + list(args)

    def _ref_or_selector(p):
        if p.get("ref") is not None:
            return ["--ref", str(p["ref"])]
        return [p["selector"]]

    cmd_map = {
        "brow_session_new": lambda p: (
            ["brow", "session", "new"]
            + (["--headed"] if p.get("headed") else [])
            + ["--profile", f"bench-{uuid.uuid4().hex[:8]}"]
            + (["--url", p["url"]] if p.get("url") else [])
        ),
        "brow_snapshot": lambda p: _cmd("snapshot", p) + (["--search", p["search"]] if p.get("search") else []),
        "brow_click": lambda p: ["brow", "click", "-s", p["session"]] + _ref_or_selector(p),
        "brow_fill": lambda p: ["brow", "fill", "-s", p["session"]] + _ref_or_selector(p) + [p["value"]],
        "brow_select": lambda p: ["brow", "select", "-s", p["session"]] + _ref_or_selector(p) + [p["value"]],
        "brow_scroll": lambda p: (
            ["brow", "scroll-to", "-s", p["session"], p["selector"]]
            if p.get("selector")
            else ["brow", "scroll", "-s", p["session"], str(p.get("pixels", 0))]
        ),
    }
    builder = cmd_map.get(name)
    if not builder:
        return None
    return builder(params)
```

- [ ] **Step 3: Update `execute_brow_tool` to parse session ID from session_new output**

The `brow session new --url` now prints session ID on first line, snapshot on subsequent lines. Update the output parsing:

```python
async def execute_brow_tool(name, params):
    import asyncio
    cmd = _build_brow_cmd(name, params)
    if cmd is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip() or f"Exit code {proc.returncode}"}
        output = stdout.decode().strip()
        # For session_new, first line is session ID, rest is snapshot
        if name == "brow_session_new" and "\n" in output:
            lines = output.split("\n", 1)
            return {"output": lines[0].strip(), "snapshot": lines[1].strip()}
        return {"output": output}
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Command timed out after 60s"}
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Update system prompt in agent.py**

In `benchmarks/harness/agent.py`, replace `BROW_INSTRUCTIONS`:

```python
BROW_INSTRUCTIONS = """You have access to brow CLI tools for browser automation.
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
  submit_answer({name: "Sony WH-1000XM5", price: "$348"})"""
```

- [ ] **Step 5: Update agent.py to extract session ID from new response format**

In `benchmarks/harness/agent.py`, update the session ID extraction (around line 172):

```python
                    if block.name == "brow_session_new" and not is_error:
                        self._brow_session_id = result.get("output", "").strip()
```

This already works since `execute_brow_tool` returns `{"output": "<session_id>"}` with the first line.

- [ ] **Step 6: Commit**

```bash
git add benchmarks/harness/tools_brow.py benchmarks/harness/agent.py
git commit -m "feat(bench): ref-based tool definitions and updated agent prompt"
```

---

### Task 7: New Fixture HTML — Deep Wizard and Data Table

**Files:**
- Create: `benchmarks/fixtures/static/deep-wizard.html`
- Create: `benchmarks/fixtures/static/data-table.html`

- [ ] **Step 1: Create deep-wizard.html**

Create `benchmarks/fixtures/static/deep-wizard.html`:

```html
<!DOCTYPE html>
<html><head><title>10-Step Registration</title></head>
<body>
<h1>Extended Registration</h1>
<div id="wizard">
  <div class="step" data-step="1"><h2>Step 1: Name</h2><input id="first-name" placeholder="First Name"><input id="last-name" placeholder="Last Name"><button class="next">Next</button></div>
  <div class="step" data-step="2" style="display:none"><h2>Step 2: Email</h2><input id="email" placeholder="Email" type="email"><input id="confirm-email" placeholder="Confirm Email" type="email"><button class="next">Next</button></div>
  <div class="step" data-step="3" style="display:none"><h2>Step 3: Phone</h2><input id="phone" placeholder="Phone"><select id="phone-type"><option value="mobile">Mobile</option><option value="home">Home</option><option value="work">Work</option></select><button class="next">Next</button></div>
  <div class="step" data-step="4" style="display:none"><h2>Step 4: Address</h2><input id="street" placeholder="Street"><input id="city" placeholder="City"><input id="zip" placeholder="ZIP"><button class="next">Next</button></div>
  <div class="step" data-step="5" style="display:none"><h2>Step 5: Preferences</h2><select id="language"><option value="en">English</option><option value="cs">Czech</option><option value="de">German</option></select><select id="timezone"><option value="UTC">UTC</option><option value="CET">CET</option><option value="EST">EST</option></select><button class="next">Next</button></div>
  <div class="step" data-step="6" style="display:none"><h2>Step 6: Notifications</h2><input type="checkbox" id="email-notif"><label for="email-notif">Email</label><input type="checkbox" id="sms-notif"><label for="sms-notif">SMS</label><input type="checkbox" id="push-notif"><label for="push-notif">Push</label><button class="next">Next</button></div>
  <div class="step" data-step="7" style="display:none"><h2>Step 7: Security</h2><input id="security-q" placeholder="Security Question"><input id="security-a" placeholder="Answer"><button class="next">Next</button></div>
  <div class="step" data-step="8" style="display:none"><h2>Step 8: Bio</h2><textarea id="bio" placeholder="Tell us about yourself" rows="3"></textarea><button class="next">Next</button></div>
  <div class="step" data-step="9" style="display:none"><h2>Step 9: Terms</h2><p>By proceeding you agree to our Terms of Service.</p><input type="checkbox" id="agree-terms"><label for="agree-terms">I agree</label><button class="next">Next</button></div>
  <div class="step" data-step="10" style="display:none"><h2>Step 10: Review</h2><div id="review-summary"></div><button id="submit-reg">Submit Registration</button></div>
  <div class="step" data-step="done" style="display:none"><h2>Registration Complete</h2><p id="confirmation">Thank you for registering! Your ID is REG-2026-0042.</p></div>
</div>
<script>
document.querySelectorAll('.next').forEach(btn => {
  btn.addEventListener('click', () => {
    const current = btn.closest('.step');
    const next = current.nextElementSibling;
    if (next) { current.style.display='none'; next.style.display='block'; }
    if (next && next.dataset.step === '10') {
      document.getElementById('review-summary').innerHTML =
        '<p>Name: ' + document.getElementById('first-name').value + ' ' + document.getElementById('last-name').value + '</p>' +
        '<p>Email: ' + document.getElementById('email').value + '</p>' +
        '<p>City: ' + document.getElementById('city').value + '</p>';
    }
  });
});
document.getElementById('submit-reg').addEventListener('click', () => {
  document.querySelector('[data-step="10"]').style.display='none';
  document.querySelector('[data-step="done"]').style.display='block';
});
</script>
</body></html>
```

- [ ] **Step 2: Create data-table.html**

Create `benchmarks/fixtures/static/data-table.html`:

```html
<!DOCTYPE html>
<html><head><title>Product Inventory</title></head>
<body>
<h1>Product Inventory</h1>
<input id="search" placeholder="Filter products..." oninput="filterTable(this.value)">
<table id="inventory">
<thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Rating</th></tr></thead>
<tbody id="tbody"></tbody>
</table>
<script>
const categories = ['Electronics','Clothing','Books','Home','Sports','Food'];
const adjectives = ['Premium','Basic','Pro','Ultra','Mini','Mega','Classic','Modern','Vintage','Smart'];
const nouns = ['Widget','Gadget','Tool','Device','Kit','Pack','Set','Bundle','Box','Unit'];
const data = [];
for (let i = 1; i <= 100; i++) {
  data.push({
    id: i,
    name: adjectives[i % adjectives.length] + ' ' + nouns[i % nouns.length] + ' ' + i,
    category: categories[i % categories.length],
    price: (10 + (i * 7.3 % 990)).toFixed(2),
    stock: (i * 13 % 500),
    rating: (3 + (i * 0.02 % 2)).toFixed(1),
  });
}
const tbody = document.getElementById('tbody');
function renderTable(items) {
  tbody.innerHTML = items.map(d =>
    '<tr><td>' + d.id + '</td><td>' + d.name + '</td><td>' + d.category + '</td><td>$' + d.price + '</td><td>' + d.stock + '</td><td>' + d.rating + '</td></tr>'
  ).join('');
}
renderTable(data);
function filterTable(q) {
  const filtered = data.filter(d => d.name.toLowerCase().includes(q.toLowerCase()) || d.category.toLowerCase().includes(q.toLowerCase()));
  renderTable(filtered);
}
</script>
</body></html>
```

- [ ] **Step 3: Commit**

```bash
git add benchmarks/fixtures/static/deep-wizard.html benchmarks/fixtures/static/data-table.html
git commit -m "feat(bench): add deep-wizard and data-table fixture HTML"
```

---

### Task 8: New Fixture HTML — SPA, Multi-Tab, Infinite Scroll, Validation Form

**Files:**
- Create: `benchmarks/fixtures/static/spa/index.html`
- Create: `benchmarks/fixtures/static/products.html`
- Create: `benchmarks/fixtures/static/infinite-scroll.html`
- Create: `benchmarks/fixtures/static/validation-form.html`

- [ ] **Step 1: Create SPA fixture**

Create `benchmarks/fixtures/static/spa/index.html`:

```html
<!DOCTYPE html>
<html><head><title>SPA Dashboard</title></head>
<body>
<nav id="nav">
  <a href="#/home" class="nav-link">Home</a>
  <a href="#/users" class="nav-link">Users</a>
  <a href="#/settings" class="nav-link">Settings</a>
  <a href="#/stats" class="nav-link">Stats</a>
</nav>
<div id="app"></div>
<script>
const views = {
  home: '<h1>Dashboard Home</h1><p>Welcome to the dashboard.</p><div class="stat">Active users: 1,234</div><div class="stat">Revenue: $56,789</div>',
  users: '<h1>User Management</h1><ul><li>Alice — admin — active</li><li>Bob — editor — active</li><li>Carol — viewer — suspended</li><li>Dave — editor — active</li><li>Eve — admin — active</li></ul>',
  settings: '<h1>Settings</h1><form id="settings-form"><label>Site Name: <input id="site-name" value="MyApp"></label><label>Theme: <select id="theme"><option value="light">Light</option><option value="dark">Dark</option></select></label><button type="button" id="save-settings">Save</button></form>',
  stats: '<h1>Statistics</h1><table><thead><tr><th>Month</th><th>Visitors</th><th>Revenue</th></tr></thead><tbody><tr><td>Jan</td><td>10,500</td><td>$12,300</td></tr><tr><td>Feb</td><td>11,200</td><td>$13,100</td></tr><tr><td>Mar</td><td>12,800</td><td>$15,600</td></tr></tbody></table>',
};
function route() {
  const hash = window.location.hash.replace('#/', '') || 'home';
  document.getElementById('app').innerHTML = views[hash] || '<h1>404 Not Found</h1>';
  if (hash === 'settings') {
    document.getElementById('save-settings')?.addEventListener('click', () => {
      document.getElementById('app').innerHTML = '<h1>Settings</h1><p id="save-confirm">Settings saved successfully!</p>';
    });
  }
}
window.addEventListener('hashchange', route);
route();
</script>
</body></html>
```

- [ ] **Step 2: Create products.html for multi-tab**

Create `benchmarks/fixtures/static/products.html`:

```html
<!DOCTYPE html>
<html><head><title>Product Catalog</title></head>
<body>
<h1>Product Catalog</h1>
<div id="products">
  <div class="product" data-id="1">
    <h2>Wireless Headphones</h2>
    <p class="price">$79.99</p>
    <p class="rating">4.5/5 (234 reviews)</p>
    <a href="/static/products.html?id=1" target="_blank" class="details-link">View Details</a>
  </div>
  <div class="product" data-id="2">
    <h2>Bluetooth Speaker</h2>
    <p class="price">$49.99</p>
    <p class="rating">4.2/5 (189 reviews)</p>
    <a href="/static/products.html?id=2" target="_blank" class="details-link">View Details</a>
  </div>
  <div class="product" data-id="3">
    <h2>USB-C Hub</h2>
    <p class="price">$34.99</p>
    <p class="rating">4.7/5 (456 reviews)</p>
    <a href="/static/products.html?id=3" target="_blank" class="details-link">View Details</a>
  </div>
</div>
<script>
const params = new URLSearchParams(window.location.search);
const id = params.get('id');
if (id) {
  const details = {
    '1': {name:'Wireless Headphones',price:'$79.99',rating:'4.5/5',reviews:234,specs:'Bluetooth 5.0, 30hr battery, ANC',sku:'WH-001'},
    '2': {name:'Bluetooth Speaker',price:'$49.99',rating:'4.2/5',reviews:189,specs:'20W output, IPX7, 12hr battery',sku:'BS-002'},
    '3': {name:'USB-C Hub',price:'$34.99',rating:'4.7/5',reviews:456,specs:'7-in-1, 4K HDMI, PD 100W',sku:'UC-003'},
  };
  const d = details[id];
  if (d) {
    document.body.innerHTML = '<h1>' + d.name + '</h1><p class="price">' + d.price + '</p><p class="rating">' + d.rating + ' (' + d.reviews + ' reviews)</p><p class="specs">Specs: ' + d.specs + '</p><p class="sku">SKU: ' + d.sku + '</p><button id="add-cart">Add to Cart</button>';
  }
}
</script>
</body></html>
```

- [ ] **Step 3: Create infinite-scroll.html**

Create `benchmarks/fixtures/static/infinite-scroll.html`:

```html
<!DOCTYPE html>
<html><head><title>Infinite Feed</title></head>
<body>
<h1>News Feed</h1>
<div id="feed"></div>
<div id="loading" style="display:none">Loading more...</div>
<script>
let page = 0;
const pageSize = 10;
const totalItems = 50;
function generateItem(i) {
  const topics = ['Technology','Science','Sports','Business','Health','Culture'];
  return {
    id: i,
    title: 'Article ' + i + ': ' + topics[i % topics.length] + ' News Update',
    summary: 'This is the summary for article ' + i + '. It covers important developments in ' + topics[i % topics.length].toLowerCase() + '.',
    author: ['Alice','Bob','Carol','Dave','Eve'][i % 5],
    date: '2026-03-' + String(1 + (i % 28)).padStart(2, '0'),
  };
}
function loadMore() {
  const start = page * pageSize + 1;
  const end = Math.min(start + pageSize - 1, totalItems);
  if (start > totalItems) return;
  const feed = document.getElementById('feed');
  for (let i = start; i <= end; i++) {
    const item = generateItem(i);
    const div = document.createElement('div');
    div.className = 'article';
    div.setAttribute('data-id', item.id);
    div.innerHTML = '<h2>' + item.title + '</h2><p>' + item.summary + '</p><span class="author">' + item.author + '</span> <span class="date">' + item.date + '</span>';
    feed.appendChild(div);
  }
  page++;
}
loadMore(); // Load first page
window.addEventListener('scroll', () => {
  if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
    document.getElementById('loading').style.display = 'block';
    setTimeout(() => {
      loadMore();
      document.getElementById('loading').style.display = 'none';
    }, 500);
  }
});
</script>
</body></html>
```

- [ ] **Step 4: Create validation-form.html**

Create `benchmarks/fixtures/static/validation-form.html`:

```html
<!DOCTYPE html>
<html><head><title>Registration with Validation</title></head>
<body>
<h1>Create Account</h1>
<form id="reg-form">
  <div class="field"><label for="username">Username:</label><input id="username" required></div>
  <div class="field"><label for="email">Email:</label><input id="email" type="email" required></div>
  <div class="field"><label for="password">Password:</label><input id="password" type="password" required></div>
  <div class="field"><label for="age">Age:</label><input id="age" type="number" min="18" max="120"></div>
  <div id="errors" style="color:red"></div>
  <div id="success" style="color:green;display:none"></div>
  <button type="button" id="register">Register</button>
</form>
<script>
document.getElementById('register').addEventListener('click', () => {
  const errors = [];
  const u = document.getElementById('username').value;
  const e = document.getElementById('email').value;
  const p = document.getElementById('password').value;
  const a = document.getElementById('age').value;
  if (!u || u.length < 3) errors.push('Username must be at least 3 characters');
  if (!e || !e.includes('@')) errors.push('Valid email is required');
  if (!p || p.length < 8) errors.push('Password must be at least 8 characters');
  if (a && (parseInt(a) < 18 || parseInt(a) > 120)) errors.push('Age must be between 18 and 120');
  const errDiv = document.getElementById('errors');
  const successDiv = document.getElementById('success');
  if (errors.length > 0) {
    errDiv.innerHTML = errors.map(e => '<p class="error">' + e + '</p>').join('');
    successDiv.style.display = 'none';
  } else {
    errDiv.innerHTML = '';
    successDiv.style.display = 'block';
    successDiv.innerHTML = '<p id="confirmation">Account created successfully for ' + u + '!</p>';
  }
});
</script>
</body></html>
```

- [ ] **Step 5: Commit**

```bash
git add benchmarks/fixtures/static/spa/ benchmarks/fixtures/static/products.html benchmarks/fixtures/static/infinite-scroll.html benchmarks/fixtures/static/validation-form.html
git commit -m "feat(bench): add SPA, multi-tab, infinite-scroll, validation-form fixtures"
```

---

### Task 9: New Task YAML Definitions

**Files:**
- Create: `benchmarks/tasks/deep-wizard.yaml`
- Create: `benchmarks/tasks/data-table-extract.yaml`
- Create: `benchmarks/tasks/spa-navigation.yaml`
- Create: `benchmarks/tasks/multi-tab-workflow.yaml`
- Create: `benchmarks/tasks/infinite-scroll.yaml`
- Create: `benchmarks/tasks/form-validation-recovery.yaml`

- [ ] **Step 1: Create deep-wizard.yaml**

```yaml
id: deep-wizard
name: "10-Step Registration Wizard"
category: throughput
url: "FIXTURE_URL/static/deep-wizard.html"
requires_fixture: true
description: |
  Navigate to FIXTURE_URL/static/deep-wizard.html.
  Complete all 10 steps of the registration wizard:
  1. Name: first='Jane', last='Smith'
  2. Email: email='jane@example.com', confirm='jane@example.com'
  3. Phone: phone='555-0123', type='work'
  4. Address: street='123 Main St', city='Prague', zip='11000'
  5. Preferences: language='Czech', timezone='CET'
  6. Notifications: check 'Email' and 'Push' (not SMS)
  7. Security: question='Pet name', answer='Fluffy'
  8. Bio: 'Software engineer from Prague'
  9. Terms: check 'I agree'
  10. Review and submit

  Return the confirmation message text as {"confirmation": "..."}.
max_steps: 25
timeout_seconds: 180
success_criteria:
  - type: structured_output
    min_fields: ["confirmation"]
    min_results: 1
tags: [wizard, multi-step, throughput]
```

- [ ] **Step 2: Create data-table-extract.yaml**

```yaml
id: data-table-extract
name: "Extract from Large Data Table"
category: extraction
url: "FIXTURE_URL/static/data-table.html"
requires_fixture: true
description: |
  Navigate to FIXTURE_URL/static/data-table.html.
  Find all products in the 'Electronics' category with a rating of 4.5 or above.
  Use the search/filter functionality or snapshot search to find relevant rows.
  Return a JSON object {"products": [...]} where each product has: id, name, category, price, stock, rating.
max_steps: 15
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["products"]
    min_results: 1
tags: [table, extraction, filtering]
```

- [ ] **Step 3: Create spa-navigation.yaml**

```yaml
id: spa-navigation
name: "SPA Dashboard Navigation"
category: navigation
url: "FIXTURE_URL/static/spa/index.html"
requires_fixture: true
description: |
  Navigate to FIXTURE_URL/static/spa/index.html.
  This is a single-page app with hash-based routing.
  1. Read the Home view — note the active users count and revenue.
  2. Navigate to Users — note how many users are listed and how many are admins.
  3. Navigate to Stats — extract the table data (months, visitors, revenue).
  4. Navigate to Settings — change the theme to 'Dark' and click Save.
  Return {"home": {"active_users": ..., "revenue": ...}, "admin_count": ..., "stats": [...], "settings_saved": true/false}.
max_steps: 20
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["home", "admin_count", "stats", "settings_saved"]
    min_results: 1
tags: [spa, navigation, extraction]
```

- [ ] **Step 4: Create multi-tab-workflow.yaml**

```yaml
id: multi-tab-workflow
name: "Multi-Tab Product Comparison"
category: interaction
url: "FIXTURE_URL/static/products.html"
requires_fixture: true
description: |
  Navigate to FIXTURE_URL/static/products.html.
  Open the 'Wireless Headphones' detail page in a new tab (click the 'View Details' link).
  From the detail page, extract: name, price, rating, specs, SKU.
  Switch back to the catalog tab and extract the price and rating of 'USB-C Hub'.
  Return {"headphones": {name, price, rating, specs, sku}, "usb_hub": {price, rating}}.
max_steps: 20
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["headphones", "usb_hub"]
    min_results: 1
tags: [multi-tab, interaction, extraction]
```

- [ ] **Step 5: Create infinite-scroll.yaml**

```yaml
id: infinite-scroll
name: "Find Article in Infinite Scroll"
category: extraction
url: "FIXTURE_URL/static/infinite-scroll.html"
requires_fixture: true
description: |
  Navigate to FIXTURE_URL/static/infinite-scroll.html.
  The page loads 10 articles at a time. Scroll down to load more articles.
  Find Article 35 and extract its title, summary, author, and date.
  Use brow_snapshot with search="Article 35" to check if it has loaded.
  Return {"article": {title, summary, author, date}}.
max_steps: 15
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["article"]
    min_results: 1
tags: [scroll, infinite, extraction]
```

- [ ] **Step 6: Create form-validation-recovery.yaml**

```yaml
id: form-validation-recovery
name: "Form with Validation Errors"
category: resilience
url: "FIXTURE_URL/static/validation-form.html"
requires_fixture: true
description: |
  Navigate to FIXTURE_URL/static/validation-form.html.
  First, try submitting with incomplete data: username='ab' (too short), no email, password='short'.
  Read the validation errors that appear.
  Then fix the errors: username='alice', email='alice@example.com', password='securepass123', age='25'.
  Submit again and verify success.
  Return {"errors_seen": [...], "confirmation": "..."} where errors_seen lists the error messages from the first attempt.
max_steps: 15
timeout_seconds: 120
success_criteria:
  - type: structured_output
    min_fields: ["errors_seen", "confirmation"]
    min_results: 1
tags: [form, validation, resilience, error-recovery]
```

- [ ] **Step 7: Commit**

```bash
git add benchmarks/tasks/deep-wizard.yaml benchmarks/tasks/data-table-extract.yaml benchmarks/tasks/spa-navigation.yaml benchmarks/tasks/multi-tab-workflow.yaml benchmarks/tasks/infinite-scroll.yaml benchmarks/tasks/form-validation-recovery.yaml
git commit -m "feat(bench): add 6 new task definitions — deep-wizard, data-table, SPA, multi-tab, scroll, validation"
```

---

### Task 10: Agent Loop — Semantic Compression

**Files:**
- Modify: `benchmarks/harness/agent.py:206-220`

- [ ] **Step 1: Update `_compress_old_results` to be semantic**

Replace the current method with tag-based compression:

```python
    def _compress_old_results(self, threshold):
        """Compress old tool results based on their type.

        - confirmation results (click/fill/select ok): compress to 1 line immediately
        - navigation results (navigate/session): compress after threshold
        - data results (snapshot/html): keep longer, compress at higher threshold
        """
        for msg in self.messages:
            if msg["role"] != "user" or not isinstance(msg.get("content"), list):
                continue
            for item in msg["content"]:
                if item.get("type") != "tool_result":
                    continue
                content = item.get("content", "")
                if not content or len(content) <= 50:
                    continue

                # Detect result type from content
                is_confirmation = content.startswith('{"ok"') or content.startswith('{"output": ""}')
                is_snapshot = '"snapshot"' in content[:100] or '"tree"' in content[:100]

                if is_confirmation and len(content) > 100:
                    # Aggressively compress action confirmations — keep first line only
                    item["content"] = content.split("\n")[0][:100]
                elif is_snapshot and len(content) > threshold * 2:
                    # Data results: higher threshold
                    lines = content.split("\n")
                    item["content"] = (
                        "\n".join(lines[:5])
                        + f"\n... ({len(lines) - 10} lines omitted) ...\n"
                        + "\n".join(lines[-5:])
                    )
                elif len(content) > threshold:
                    lines = content.split("\n")
                    item["content"] = (
                        "\n".join(lines[:5])
                        + f"\n... ({len(lines) - 10} lines omitted) ...\n"
                        + "\n".join(lines[-5:])
                    )
```

- [ ] **Step 2: Run existing benchmark tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest benchmarks/tests/ -v`

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add benchmarks/harness/agent.py
git commit -m "feat(bench): semantic compression — aggressive for confirmations, lenient for data"
```

---

### Task 11: Run Tests and Verify Everything Works

**Files:** None (verification only)

- [ ] **Step 1: Run brow unit tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest brow/tests/ -v`

Expected: All PASS

- [ ] **Step 2: Run benchmark unit tests**

Run: `cd /Users/danherma/projects-personal/brow && python -m pytest benchmarks/tests/ -v`

Expected: All PASS

- [ ] **Step 3: Manual smoke test — session new with url**

Run: `cd /Users/danherma/projects-personal/brow && brow daemon stop; brow daemon start && sleep 2 && brow session new --url "data:text/html,<body><a href='/'>Home</a><button>Click</button></body>"`

Expected: Prints session ID, then snapshot with `[1] a "Home"` and `[2] button "Click"`

- [ ] **Step 4: Manual smoke test — click by ref**

Run: `brow -s 1 click --ref 2`

Expected: Prints updated snapshot

- [ ] **Step 5: Cleanup**

Run: `brow session delete 1`

- [ ] **Step 6: Final commit with any fixes**

If any adjustments were needed, commit them:

```bash
git add -u
git commit -m "fix: address issues found during integration testing"
```

---

### Task 12: Run Benchmarks and Update README

**Files:**
- Modify: `benchmarks/README.md`

- [ ] **Step 1: Run brow benchmark on all fixture tasks**

Run: `cd /Users/danherma/projects-personal/brow && python -m benchmarks.run --backend brow --runs 1 --output benchmarks/results_v2/`

This runs all 16 fixture tasks (10 original + 6 new).

- [ ] **Step 2: Run playwright-cli benchmark on all fixture tasks**

Run: `cd /Users/danherma/projects-personal/brow && python -m benchmarks.run --backend playwright-cli --runs 1 --output benchmarks/results_v2_pwcli/`

- [ ] **Step 3: Compare results and update README.md**

Update the results tables in `benchmarks/README.md` with the new numbers. Include both original 10 tasks and new 6 tasks.

- [ ] **Step 4: Commit results**

```bash
git add benchmarks/results_v2/ benchmarks/results_v2_pwcli/ benchmarks/README.md
git commit -m "bench: run v2 benchmarks with ref engine — brow vs playwright-cli"
```

- [ ] **Step 5: Push**

```bash
git push
```
