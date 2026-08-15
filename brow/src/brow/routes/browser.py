import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from brow.config import DEFAULT_TIMEOUT, SCREENSHOTS_DIR, ensure_dirs
from brow.snapshot import filter_lines, format_tree

router = APIRouter(prefix="/browser/{sid}", tags=["browser"])

SNAPSHOT_JS = """
() => {
    document.querySelectorAll('[data-brow-ref]').forEach(el => el.removeAttribute('data-brow-ref'));

    const INTERACTIVE = new Set([
        'a', 'button', 'input', 'select', 'textarea', 'option',
        'details', 'summary', 'dialog', 'menu', 'menuitem',
    ]);
    const INTERACTIVE_ROLES = new Set([
        'button', 'tab', 'link', 'menuitem', 'option', 'switch',
        'checkbox', 'radio', 'slider', 'spinbutton', 'combobox',
        'searchbox', 'textbox',
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
        NODE_LIMIT = 300;
    }

    let nodeCount = 0;
    let refCounter = 0;
    const skipNonInteractive = interactiveCount > 150;

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
            try {
                const c = buildTree(child, depth + 1);
                if (c) children.push(c);
            } catch (e) { /* skip unprocessable node */ }
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

        // When interactive-dense, skip non-interactive non-semantic nodes sooner
        if (skipNonInteractive && !isInteractive && nodeCount > NODE_LIMIT * 0.7) {
            if (children.length === 0) return null;
            return { role: 'group', children };
        }

        nodeCount++;
        const obj = { role };
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

        // List compression: inline >5 same-type simple children
        if (children.length > 5) {
            const roles = children.map(c => c.role);
            const firstRole = roles[0];
            const allSame = roles.every(r => r === firstRole);
            const allSimple = children.every(c => !c.children || c.children.every(gc => gc.role === 'text'));
            if (allSame && allSimple) {
                return { role: 'inline-list', itemRole: firstRole, items: children };
            }
        }

        return obj;
    }

    let tree = null;
    try {
        tree = buildTree(document.body, 0);
    } catch (e) {
        // Fallback: return minimal tree on crash
        tree = { role: 'text', name: 'Snapshot error: ' + e.message };
    }
    return { tree, truncated: nodeCount >= NODE_LIMIT, nodeCount, refCount: refCounter, interactiveCount };
}
"""


async def _take_snapshot(page, search=None):
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    try:
        result = await page.evaluate(SNAPSHOT_JS)
    except Exception:
        result = {
            "tree": {"role": "text", "name": "Snapshot unavailable (page too complex)"},
            "truncated": True,
            "nodeCount": 0,
        }
    tree = result.get("tree") if isinstance(result, dict) else result
    truncated = result.get("truncated", False) if isinstance(result, dict) else False
    node_count = result.get("nodeCount", 0) if isinstance(result, dict) else 0
    formatted = format_tree(tree) if tree else ""
    if search:
        formatted = filter_lines(formatted, search)
    return formatted, truncated, node_count


def _get_session(req, sid):
    try:
        return req.app.state.manager.get(sid)
    except KeyError:
        raise HTTPException(404, f"Session {sid} not found")


def _get_page(session):
    page = session.page
    if not page:
        raise HTTPException(400, "No active page")
    return page


_REF_RE = re.compile(r"^\s*\[?(\d+)\]?\s*$")


def _resolve_selector(body):
    if hasattr(body, "ref") and body.ref is not None:
        return f'[data-brow-ref="{body.ref}"]'
    if hasattr(body, "selector") and body.selector is not None:
        m = _REF_RE.match(body.selector)
        if m:
            return f'[data-brow-ref="{m.group(1)}"]'
        return body.selector
    raise HTTPException(400, "Either 'ref' or 'selector' must be provided")


def _log_action(session, action: str, **kwargs):
    actions = session.state.setdefault("actions", [])
    entry = {"seq": len(actions) + 1, "action": action}
    entry.update({k: v for k, v in kwargs.items() if v is not None})
    actions.append(entry)


class NavigateReq(BaseModel):
    url: str
    timeout: int = DEFAULT_TIMEOUT
    wait: str = "load"


class WaitReq(BaseModel):
    selector: Optional[str] = None
    load: bool = False
    timeout: int = DEFAULT_TIMEOUT


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


class TypeReq(BaseModel):
    text: str


class KeyReq(BaseModel):
    key: str


class HoverReq(BaseModel):
    selector: str
    timeout: int = DEFAULT_TIMEOUT


class ScrollReq(BaseModel):
    pixels: int = 0
    selector: Optional[str] = None


class ScrollUntilReq(BaseModel):
    until: str
    pixels: int = 800
    max_attempts: int = 10
    timeout: int = DEFAULT_TIMEOUT


class ClickUntilReq(BaseModel):
    selector: str
    until_gone: Optional[str] = None
    max_iterations: int = 25
    settle_ms: int = 500
    timeout: int = DEFAULT_TIMEOUT


class DragReq(BaseModel):
    source: str
    target: str


class UploadReq(BaseModel):
    selector: str
    filepath: str


class SelectReq(BaseModel):
    selector: Optional[str] = None
    ref: Optional[int] = None
    value: str
    timeout: int = DEFAULT_TIMEOUT


class ScreenshotReq(BaseModel):
    full: bool = False
    path: Optional[str] = None
    width: Optional[int] = None
    scale: Optional[float] = None
    quality: Optional[str] = None


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
    status = r.status if r else None
    if body.wait in ("load", "networkidle"):
        try:
            await page.wait_for_load_state(body.wait, timeout=min(body.timeout, 10000))
        except Exception:
            pass
    _log_action(session, "navigate", url=body.url, status=status)
    formatted, truncated, node_count = await _take_snapshot(page)
    resp = {"url": page.url, "status": status, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
        resp["hint"] = f"Page has {node_count}+ nodes. Use search param to filter."
    return resp


@router.post("/wait")
async def wait(req: Request, sid: str, body: WaitReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    if body.load:
        await page.wait_for_load_state(timeout=body.timeout)
    elif body.selector:
        await page.wait_for_selector(body.selector, timeout=body.timeout)
    return {"ok": True}


@router.get("/url")
async def get_url(req: Request, sid: str):
    session = _get_session(req, sid)
    page = _get_page(session)
    return {"url": page.url}


@router.get("/snapshot")
async def snapshot(
    req: Request, sid: str, search: Optional[str] = None, locator: Optional[str] = None, compact: bool = False
):
    session = _get_session(req, sid)
    page = _get_page(session)
    formatted, truncated, node_count = await _take_snapshot(page, search=search)
    lines = formatted.split("\n")
    large = len(lines) > 500
    if (compact or large) and not search:
        interactive_lines = [ln for ln in lines if "[" in ln and "]" in ln]
        context_lines = [ln for ln in lines if any(k in ln for k in ("heading", "navigation", "main", "form"))]
        kept = list(dict.fromkeys(interactive_lines + context_lines))[:300]
        header = f"[Showing {len(kept)} of {len(lines)} lines — use --search <regex> to filter]\n"
        formatted = header + "\n".join(kept)
        truncated = True
    resp = {"tree": formatted}
    if truncated:
        resp["truncated"] = True
        resp["hint"] = f"Page has {node_count}+ nodes ({len(lines)} lines). Use --search to filter."
    return resp


@router.post("/screenshot")
async def screenshot(req: Request, sid: str, body: ScreenshotReq):
    from PIL import Image

    session = _get_session(req, sid)
    page = _get_page(session)
    ensure_dirs()
    if body.path:
        path = Path(body.path)
    else:
        path = SCREENSHOTS_DIR / f"{sid}-{int(time.time())}.png"

    await page.screenshot(path=str(path), full_page=body.full)

    if body.width or body.scale or body.quality:
        img = Image.open(path)

        if body.quality:
            presets = {"low": 400, "medium": 800, "high": 1200}
            target_width = presets.get(body.quality, 800)
        elif body.width:
            target_width = body.width
        elif body.scale:
            target_width = int(img.width * body.scale)
        else:
            target_width = img.width

        if target_width != img.width:
            aspect_ratio = img.height / img.width
            target_height = int(target_width * aspect_ratio)
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            img.save(path, optimize=True, quality=85)

    return {"path": str(path)}


@router.get("/html")
async def get_html(req: Request, sid: str, locator: Optional[str] = None, search: Optional[str] = None):
    session = _get_session(req, sid)
    page = _get_page(session)
    if locator:
        el = page.locator(locator)
        html = await el.inner_html()
    else:
        html = await page.content()
    if search:
        html = filter_lines(html, search)
    return {"html": html}


@router.get("/logs")
async def get_logs(req: Request, sid: str, search: Optional[str] = None, count: int = 50):
    session = _get_session(req, sid)
    logs = session.state.get("console_logs", [])
    text = "\n".join(logs[-count:])
    if search:
        text = filter_lines(text, search)
    return {"logs": text}


_STATIC_PREFIXES = ("image/", "font/", "text/css", "application/javascript", "text/javascript", "application/font")


@router.get("/network")
async def get_network(
    req: Request,
    sid: str,
    search: Optional[str] = None,
    count: int = 50,
    include_static: bool = False,
    include_response: bool = False,
):
    import re

    session = _get_session(req, sid)
    reqs = session.state.get("network_requests", [])
    if not include_static:
        reqs = [r for r in reqs if not any(r["type"].startswith(p) for p in _STATIC_PREFIXES)]
    if search:
        pattern = re.compile(search)
        reqs = [r for r in reqs if pattern.search(r["url"]) or pattern.search(r["type"])]
    reqs = reqs[-count:]
    lines = []
    for r in reqs:
        line = f"{r['method']:<6} {r['status']}  {r['type']:<30} {r['url']}"
        if include_response and r.get("response_preview"):
            line += f"\n    {r['response_preview'][:200]}"
        lines.append(line)
    return {"network": "\n".join(lines)}


@router.delete("/network")
async def clear_network(req: Request, sid: str):
    session = _get_session(req, sid)
    session.state["network_requests"] = []
    return {"ok": True}


class FetchReq(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[dict] = None
    body: Optional[str] = None
    no_cookies: bool = False


@router.post("/fetch")
async def fetch_url(req: Request, sid: str, body: FetchReq):
    session = _get_session(req, sid)
    if body.no_cookies:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            r = await client.request(
                body.method,
                body.url,
                headers=body.headers or {},
                content=body.body,
            )
        result = {"status": r.status_code, "contentType": r.headers.get("content-type", ""), "body": r.text}
        _log_action(session, "fetch", url=body.url, method=body.method, no_cookies=True, status=r.status_code)
        return result
    page = _get_page(session)
    js = """
async ({url, method, headers, body}) => {
    const opts = {method, headers: headers || {}};
    if (body) opts.body = body;
    const r = await fetch(url, opts);
    const text = await r.text();
    return {status: r.status, contentType: r.headers.get('content-type') || '', body: text};
}
"""
    result = await page.evaluate(
        js, {"url": body.url, "method": body.method, "headers": body.headers or {}, "body": body.body}
    )
    _log_action(session, "fetch", url=body.url, method=body.method, no_cookies=False, status=result.get("status"))
    return result


@router.get("/websocket")
async def get_websocket(req: Request, sid: str, search: Optional[str] = None, count: int = 50):
    session = _get_session(req, sid)
    msgs = session.state.get("websocket_messages", [])[-count:]
    lines = [f"{m['direction'].upper():<4}  {m['url']}\n      {m['data'][:200]}" for m in msgs]
    text = "\n".join(lines)
    if search:
        text = filter_lines(text, search)
    return {"websocket": text}


@router.delete("/websocket")
async def clear_websocket(req: Request, sid: str):
    session = _get_session(req, sid)
    session.state["websocket_messages"] = []
    return {"ok": True}


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
            _log_action(session, "click", selector=selector)
            # Wait for navigation if it occurs; otherwise sleep briefly to allow
            # hash-routing / JS DOM mutations to settle before snapshotting.
            try:
                await page.wait_for_load_state("load", timeout=300)
            except Exception:
                await aio.sleep(0.15)
            formatted, truncated, _ = await _take_snapshot(page)
            resp = {"ok": True, "snapshot": formatted}
            if truncated:
                resp["truncated"] = True
            return resp
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500, f"Failed to click selector '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
    )


@router.post("/fill")
async def fill(req: Request, sid: str, body: FillReq):
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

            await page.fill(selector, body.value, timeout=body.timeout)
            _log_action(session, "fill", selector=selector, value=body.value)
            formatted, truncated, _ = await _take_snapshot(page)
            resp = {"ok": True, "snapshot": formatted}
            if truncated:
                resp["truncated"] = True
            return resp
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                await aio.sleep(1)

    raise HTTPException(
        500, f"Failed to fill selector '{selector}' after {attempts} attempts. Last error: {str(last_error)}"
    )


@router.post("/type")
async def type_text(req: Request, sid: str, body: TypeReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.keyboard.type(body.text)
    return {"ok": True}


@router.post("/key")
async def press_key(req: Request, sid: str, body: KeyReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.keyboard.press(body.key)
    _log_action(session, "key", key=body.key)
    formatted, truncated, _ = await _take_snapshot(page)
    resp = {"ok": True, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
    return resp


@router.post("/hover")
async def hover(req: Request, sid: str, body: HoverReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.hover(body.selector, timeout=body.timeout)
    return {"ok": True}


@router.post("/scroll")
async def scroll(req: Request, sid: str, body: ScrollReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    if body.selector:
        await page.locator(body.selector).scroll_into_view_if_needed()
    else:
        await page.evaluate(f"window.scrollBy(0, {body.pixels})")
    return {"ok": True}


@router.post("/scroll-until")
async def scroll_until(req: Request, sid: str, body: ScrollUntilReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    for attempt in range(body.max_attempts):
        try:
            loc = page.locator(body.until)
            if await loc.count() > 0 and await loc.first.is_visible():
                await loc.first.scroll_into_view_if_needed()
                return {"ok": True, "found": True, "attempts": attempt + 1}
        except Exception:
            pass
        await page.evaluate(f"window.scrollBy(0, {body.pixels})")
        await page.wait_for_timeout(500)
    return {"ok": True, "found": False, "attempts": body.max_attempts}


@router.post("/click-until")
async def click_until(req: Request, sid: str, body: ClickUntilReq):
    """Click a selector repeatedly until the work runs out.

    Bulk UI work is nearly always this shape: act on the visible batch, the list
    refills, act again. Driving that from outside costs a process launch plus an
    HTTP round trip per iteration and needs hand-written stop conditions, so this
    keeps the loop next to the browser.

    Stops on `until_gone` disappearing, on the clickable itself vanishing, or on
    max_iterations. `done` distinguishes "finished" from "gave up", and `reason`
    says which, so a truncated sweep is never mistaken for a complete one.
    """
    session = _get_session(req, sid)
    page = _get_page(session)

    iterations = 0
    reason = "until_gone cleared"
    done = False

    for _ in range(body.max_iterations):
        if body.until_gone:
            try:
                if await page.locator(body.until_gone).count() == 0:
                    done = True
                    break
            except Exception as e:
                raise HTTPException(400, f"Invalid until_gone selector '{body.until_gone}': {e}")

        target = page.locator(body.selector)
        try:
            if await target.count() == 0:
                done = True
                reason = "clickable is gone"
                break
        except Exception as e:
            raise HTTPException(400, f"Invalid selector '{body.selector}': {e}")

        try:
            await target.first.click(timeout=body.timeout)
        except Exception as e:
            # Report progress made so far rather than losing it to an exception.
            return {
                "ok": False,
                "done": False,
                "iterations": iterations,
                "reason": f"click failed on iteration {iterations + 1}: {e}",
            }
        iterations += 1
        await page.wait_for_timeout(body.settle_ms)
    else:
        reason = f"hit max_iterations ({body.max_iterations}) — work may remain, re-run to continue"

    if body.until_gone and not done:
        try:
            done = await page.locator(body.until_gone).count() == 0
            if done:
                reason = "until_gone cleared"
        except Exception:
            pass

    _log_action(session, "click-until", selector=body.selector, iterations=iterations)
    return {"ok": True, "done": done, "iterations": iterations, "reason": reason}


@router.post("/drag")
async def drag(req: Request, sid: str, body: DragReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.drag_and_drop(body.source, body.target)
    return {"ok": True}


@router.post("/select")
async def select_option(req: Request, sid: str, body: SelectReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    selector = _resolve_selector(body)
    await page.select_option(selector, body.value, timeout=body.timeout)
    _log_action(session, "select", selector=selector, value=body.value)
    formatted, truncated, _ = await _take_snapshot(page)
    resp = {"ok": True, "snapshot": formatted}
    if truncated:
        resp["truncated"] = True
    return resp


@router.post("/upload")
async def upload(req: Request, sid: str, body: UploadReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    await page.set_input_files(body.selector, body.filepath)
    _log_action(session, "upload", selector=body.selector, filepath=body.filepath)
    return {"ok": True}


@router.get("/actions")
async def get_actions(req: Request, sid: str, as_json: bool = False):
    session = _get_session(req, sid)
    actions = session.state.get("actions", [])
    if as_json:
        return {"actions": actions}
    lines = []
    for a in actions:
        s, act = a["seq"], a["action"]
        if act == "navigate":
            lines.append(f"{s:<3} navigate  {a.get('url', '')}  [{a.get('status', '')}]")
        elif act == "fetch":
            nc = " --no-cookies" if a.get("no_cookies") else ""
            lines.append(f"{s:<3} fetch     {a.get('url', '')}  [{a.get('status', '')}]{nc}")
        elif act == "click":
            lines.append(f"{s:<3} click     {a.get('selector', '')}")
        elif act == "fill":
            lines.append(f"{s:<3} fill      {a.get('selector', '')}  value={str(a.get('value', ''))[:40]!r}")
        elif act == "key":
            lines.append(f"{s:<3} key       {a.get('key', '')}")
        elif act == "select":
            lines.append(f"{s:<3} select    {a.get('selector', '')}  value={a.get('value', '')!r}")
        elif act == "upload":
            lines.append(f"{s:<3} upload    {a.get('selector', '')}  file={a.get('filepath', '')}")
        else:
            lines.append(f"{s:<3} {act}")
    return {"actions": "\n".join(lines)}


@router.delete("/actions")
async def clear_actions(req: Request, sid: str):
    session = _get_session(req, sid)
    session.state["actions"] = []
    return {"ok": True}


class ReplayReq(BaseModel):
    playbook: dict
    vars: dict = {}


def _sub(val, variables):
    if not isinstance(val, str):
        return val

    def repl(m):
        name, _, key = m.group(1).partition("[")
        v = variables.get(name)
        if key:
            key = key.rstrip("]")
            if isinstance(v, dict):
                v = v.get(key)
            elif isinstance(v, list):
                try:
                    v = v[int(key)]
                except (ValueError, IndexError):
                    v = None
            else:
                v = None
        if v is None and name not in variables:
            return m.group(0)
        return str(v)

    return re.sub(r"\{([^{}]+)\}", repl, val)


async def _run_replay_steps(page, session, steps, variables, base_url, stop_on_failure=False, default_auth=None):
    def sub(val):
        return _sub(val, variables)

    def resolve_url(u):
        u = sub(u)
        return u if u.startswith("http") else base_url + u

    results = []
    for step in steps:
        act = step["action"]
        entry = {"action": act, "ok": False}
        try:
            if act == "navigate":
                url = resolve_url(step["url"])
                r = await page.goto(url, timeout=step.get("timeout", 30000))
                entry.update({"url": url, "status": r.status if r else None, "ok": True})
                _log_action(session, "navigate", url=url, status=r.status if r else None)
            elif act == "click":
                await page.click(sub(step["selector"]))
                _log_action(session, "click", selector=sub(step["selector"]))
                entry["ok"] = True
            elif act == "fill":
                await page.fill(sub(step["selector"]), sub(step["value"]))
                _log_action(session, "fill", selector=sub(step["selector"]), value=sub(step["value"]))
                entry["ok"] = True
            elif act == "key":
                await page.keyboard.press(sub(step["key"]))
                _log_action(session, "key", key=sub(step["key"]))
                entry["ok"] = True
            elif act == "select":
                await page.select_option(sub(step["selector"]), sub(step["value"]))
                _log_action(session, "select", selector=sub(step["selector"]), value=sub(step["value"]))
                entry["ok"] = True
            elif act == "fetch":
                url = resolve_url(step["url"])
                method = step.get("method", "GET")
                no_cookies = step.get("auth", default_auth) == "none"
                headers = {k: sub(v) for k, v in step.get("headers", {}).items()}
                if no_cookies:
                    import httpx

                    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=headers) as client:
                        r = await client.request(method, url)
                    data_text, status = r.text, r.status_code
                else:
                    js = (
                        "async ({url,method,headers})=>{"
                        "const r=await fetch(url,{method,headers});"
                        "return {status:r.status,body:await r.text()}}"
                    )
                    r = await page.evaluate(js, {"url": url, "method": method, "headers": headers})
                    data_text, status = r["body"], r["status"]
                _log_action(session, "fetch", url=url, method=method, no_cookies=no_cookies, status=status)
                expect_status = step.get("expect_status")
                ok = status in expect_status if expect_status else status < 400
                entry.update({"url": url, "status": status, "ok": ok})
                if not ok:
                    entry["error"] = f"HTTP {status}"
                if step.get("output"):
                    import json as _json

                    try:
                        data = _json.loads(data_text)
                    except Exception:
                        data = data_text
                    entry["data"] = data
                    variables[step["output"]] = data
            elif act == "wait":
                if step.get("selector"):
                    await page.wait_for_selector(
                        sub(step["selector"]), state=step.get("state", "visible"), timeout=step.get("timeout", 30000)
                    )
                else:
                    await page.wait_for_timeout(step.get("ms", 1000))
                entry["ok"] = True
            elif act == "assert":
                await page.wait_for_selector(
                    sub(step["selector"]), state=step.get("state", "visible"), timeout=step.get("timeout", 5000)
                )
                entry["ok"] = True
            elif act == "for_each":
                var = step["var"]
                items = step.get("items")
                if isinstance(items, str):
                    items = variables.get(items, [])
                nested_failed = False
                for item in items:
                    variables[var] = item
                    nested_results = await _run_replay_steps(
                        page, session, step["steps"], variables, base_url, stop_on_failure, default_auth
                    )
                    results.extend(nested_results)
                    if stop_on_failure and any(not r["ok"] for r in nested_results):
                        nested_failed = True
                        break
                variables.pop(var, None)
                if nested_failed:
                    break
                continue
            else:
                entry["error"] = f"unknown action: {act!r}"
        except Exception as e:
            entry["error"] = str(e)
        results.append(entry)
        if not entry["ok"] and stop_on_failure:
            break
    return results


@router.post("/replay")
async def replay(req: Request, sid: str, body: ReplayReq):
    session = _get_session(req, sid)
    page = _get_page(session)
    base_url = body.playbook.get("base_url", "")
    variables = {**body.playbook.get("vars", {}), **body.vars}

    results = await _run_replay_steps(
        page,
        session,
        body.playbook.get("steps", []),
        variables,
        base_url,
        stop_on_failure=bool(body.playbook.get("stop_on_failure")),
        default_auth=body.playbook.get("auth"),
    )
    return {"results": results}
